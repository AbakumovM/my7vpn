# Платёжная система

---

## Провайдеры платежей

| Провайдер | Файл | Флаг включения |
|-----------|------|----------------|
| YooKassa | `src/infrastructure/yookassa/client.py` | `app_config.yookassa.enabled` |
| YuMoney (legacy) | `src/infrastructure/yumoney/quickpay.py` | `app_config.yumoney.enabled` |
| Ручная оплата (QR) | — | по умолчанию если оба disabled |

---

## PendingPayment — паттерн ожидания

**Таблица:** `pending_payments`
**Файл:** `src/apps/device/domain/models.py` → `PendingPayment`

```python
PendingPayment:
    user_telegram_id: int
    action: str            # "new" | "renew"
    device_type: str       # "vpn"
    device_name: str | None
    duration: int          # месяцев
    amount: int            # сумма к оплате (0 = бонус покрывает всё)
    balance_to_deduct: int # списать с бонусного счёта
    device_limit: int      # 1-3
    created_at: datetime
    id: int | None
```

**Жизненный цикл:**
```
create_pending_payment()  →  [ожидание оплаты]  →  confirm_payment() / reject_payment()
     ↓                              ↓                        ↓
  запись в БД              вебхук / кнопка админа      удаление из БД
```

---

## YooKassa (автоплатежи)

**Создание платежа:**
```python
# src/infrastructure/yookassa/client.py
payment = await yookassa_client.create_payment(amount=N, pending_id=X)
# → payment.confirmation_url  (отправляем пользователю)
# → payment.payment_id       (хранится в метаданных ЮKassa)
```

**Вебхук:** `POST /api/v1/payments/yookassa/webhook`
**Файл:** `src/apps/device/controllers/http/yookassa_router.py`

Процесс:
1. Проверить `event == "payment.succeeded"`
2. Извлечь `pending_id` из `object.metadata["pending_id"]`
3. Верифицировать статус через API ЮKassa: `get_payment_status(payment_id) == "succeeded"`
4. `interactor.confirm_payment(pending_id)`
5. Уведомить пользователя в боте (`subscription_url` или `end_date`)
6. Начислить бонус рефереру (если первая покупка)
7. Уведомить админа

---

## YuMoney (legacy, QR-оплата)

**Файл:** `src/infrastructure/yumoney/quickpay.py`

- `build_quickpay_url(settings, amount, pending_id)` — строит URL для оплаты
- `verify_notification_signature(...)` — проверяет SHA1 подпись уведомлений

При оплате через QR/YuMoney → **подтверждение через админа** (кнопки ✅/❌).

---

## Ручная оплата (QR-код)

Когда `yookassa.enabled = False` и `yumoney.enabled = False`:
1. Показать QR-код из файла `app_config.payment.payment_qr`
2. Создать `PendingPayment`
3. Отправить уведомление админу с кнопками `AdminConfirmCallback`
4. Дождаться подтверждения

---

## Случай payment == 0 (бонусный счёт покрывает всё)

Когда `user.balance >= price`:
- `finally_payment = 0`
- Пропустить всех провайдеров
- Сразу `create_pending_payment(amount=0)` → `confirm_payment()`
- Источник: `src/apps/device/controllers/bot/router.py`, шаг 5

---

## Калькулятор оплаты (шаг 3 бот-флоу)

```python
price             = TARIFF_MATRIX[device_limit][duration]
user_balance      = await user_view.get_balance(telegram_id)

finally_payment   = max(price - user_balance, 0)   # реальная оплата
balance_to_deduct = min(user_balance, price)        # списывается с бонусов
bonus_used        = balance_to_deduct               # = price - finally_payment
```

**Пример:** цена 300₽, баланс 100₽ → к оплате 200₽, списать 100 бонусов.

---

## Тарифы

**Файл:** `src/common/bot/keyboards/user_actions.py` → `TARIFF_MATRIX`

```python
TARIFF_MATRIX = {
    device_limit: {
        1: price_1m,
        3: price_3m,
        6: price_6m,
        12: price_12m,
    }
}
```

---

## Методы интерактора

**Файл:** `src/apps/device/application/interactor.py`

| Метод | Команда | Результат |
|-------|---------|-----------|
| `create_pending_payment()` | `CreatePendingPayment` | `PendingPaymentInfo` |
| `confirm_payment()` | `ConfirmPayment(pending_id)` | `ConfirmPaymentResult` |
| `reject_payment()` | `RejectPayment(pending_id)` | `PendingPaymentInfo` |

**ConfirmPaymentResult:**
```python
ConfirmPaymentResult:
    user_telegram_id: int
    action: str                  # "new" | "renew"
    subscription_url: str | None
    end_date: datetime
    referrer_telegram_id: int | None
```
