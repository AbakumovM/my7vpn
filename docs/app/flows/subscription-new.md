# Покупка новой подписки

**Точка входа:** кнопка "🚀 Подключить VPN" → `VpnCallback(action="new")`
**Файл:** `src/apps/device/controllers/bot/router.py` → `handle_vpn_flow()`

---

## Шаги флоу

### Шаг 1 — Выбор количества устройств
- Триггер: `VpnCallback(action=VpnAction.NEW, device_limit=None)`
- Показать клавиатуру: `get_keyboard_device_count(action="new")`
- Варианты: 1, 2, 3 устройства (3 = хит)

### Шаг 2 — Выбор тарифа
- Триггер: `VpnCallback(action="new", device_limit=X, duration=0)`
- Показать клавиатуру: `get_keyboard_tariff(action="new", device_limit=X)`
- Варианты: 1, 3, 6, 12 месяцев (цены из `TARIFF_MATRIX`)

### Шаг 3 — Подтверждение оплаты
- Получить баланс: `user_view.get_balance(telegram_id)`
- Расчёт:
  ```
  finally_payment    = max(price - balance, 0)  # сколько платит
  balance_to_deduct  = min(balance, price)       # списывается с бонусов
  ```
- Клавиатура: `get_keyboard_confirm_payment(...)`
- Текст: `bot_repl.get_confirm_payment(price, finally_payment, bonus_used)`

### Шаг 4 — Отмена (choice=NO или payment_status=FAILED)
- Возврат в главное меню

### Шаг 5 — Выполнение платежа (choice=YES)

#### Вариант A: payment == 0 (бонусов достаточно)
```
create_pending_payment(amount=0, balance_to_deduct=X)
  → confirm_payment(pending_id)
  → отправить subscription_url
```

#### Вариант B: payment > 0, yookassa.enabled = True
```
create_pending_payment(amount=N, ...)
  → yookassa_client.create_payment(amount, pending_id)
  → отправить ссылку оплаты пользователю
  → ожидать вебхук /api/v1/payments/yookassa/webhook
  → confirm_payment(pending_id)
  → отправить subscription_url
```

#### Вариант C: payment > 0, yookassa.enabled = False (ручная оплата)
```
create_pending_payment(amount=N, ...)
  → показать QR-код (app_config.payment.payment_qr)
  → пользователь оплачивает вручную
  → admin получает уведомление с кнопками ✅/❌
  → confirm_payment(pending_id)
  → отправить subscription_url
```

---

## Что происходит при confirm_payment

**Файл:** `src/apps/device/application/interactor.py` → `confirm_payment()`

1. Загрузить PendingPayment из БД
2. Списать баланс: `user.balance -= pending.balance_to_deduct`
3. Создать/обновить Remnawave аккаунт:
   - Если `user.remnawave_uuid is None` → `remnawave_gateway.create_user(telegram_id, expire_at, device_limit)`
   - Иначе → `remnawave_gateway.update_user(uuid, expire_at, device_limit)`
4. Сохранить `remnawave_uuid` и `subscription_url` в User
5. Создать `UserSubscription` (plan=months, end_date=now+months)
6. Создать `UserPayment` (amount, duration, payment_method="карта")
7. Начислить бонус рефереру (если первая платная покупка):
   - `count_payments_for_user(telegram_id) == 0`
   - `user.referred_by is not None`
   - `referrer.balance += 50`
8. Удалить PendingPayment из БД
9. Вернуть `ConfirmPaymentResult(subscription_url, end_date, action, referrer_telegram_id)`

---

## Результат для пользователя (action="new")
```
✅ Оплата прошла успешно!
Ваша ссылка для подключения — скопируйте и вставьте в приложение Happ:
<code>{subscription_url}</code>
```
Клавиатура: `get_keyboard_vpn_received()` (кнопки: Инструкция, Главное меню)

---

## Ключевые файлы
| Файл | Назначение |
|------|-----------|
| `src/apps/device/controllers/bot/router.py` | Bot handlers (handle_vpn_flow, handle_admin_confirm) |
| `src/apps/device/application/interactor.py` | confirm_payment, create_pending_payment |
| `src/apps/device/domain/models.py` | PendingPayment, UserSubscription, UserPayment |
| `src/apps/device/adapters/gateway.py` | SQLAlchemySubscriptionGateway |
| `src/infrastructure/remnawave/client.py` | create_user, update_user |
| `src/infrastructure/yookassa/client.py` | create_payment |
| `src/common/bot/keyboards/keyboards.py` | get_keyboard_device_count, get_keyboard_tariff, get_keyboard_confirm_payment |
| `src/common/bot/keyboards/user_actions.py` | TARIFF_MATRIX |
