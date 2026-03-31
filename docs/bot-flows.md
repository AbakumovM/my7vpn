# Bot Flows

Все сценарии взаимодействия с Telegram-ботом. Точка входа: `main_bot.py`.

## Callback Data

Основной callback: `VpnCallback(prefix="vpn")` из `src/common/bot/cbdata.py`

| Поле | Тип | Описание |
|------|-----|----------|
| `action` | `VpnAction` | `new`, `renew`, `referral` |
| `device` | `str` | Тип: `iOS`, `Android`, `TV`, `Windows`, `MacOS` |
| `device_name` | `str \| None` | Имя конкретного устройства (для renew) |
| `duration` | `int` | Срок в месяцах (1, 3, 6, 12) |
| `referral_id` | `int \| None` | telegram_id реферера |
| `payment` | `int \| None` | Сумма платежа |
| `balance` | `int \| None` | Остаток баланса после вычета |
| `choice` | `ChoiceType` | `yes`, `no`, `stop` |
| `payment_status` | `PaymentStatus` | `success`, `failed` |

## FSM States (`src/common/bot/states.py`)

| Группа | State | Когда |
|--------|-------|-------|
| `RegisterVpn` | `chooising_devise` | Выбор типа устройства (не используется в текущем коде) |
| `RegisterVpn` | `chooising_plan` | Выбор тарифа (не используется в текущем коде) |
| `EmailInput` | `waiting_for_email` | Ожидание ввода email перед оплатой |

## Тарифы (`src/common/bot/keyboards/user_actions.py`)

| Тариф | Цена (руб) |
|-------|------------|
| 1 месяц | 150 |
| 3 месяца | 400 |
| 6 месяцев | 700 |
| 12 месяцев | 1200 |

---

## Flow 1: `/start` — новый пользователь

**Router**: `src/apps/user/controllers/bot/router.py`

```
/start → get_or_create(telegram_id) → device_count == 0?
  ├─ Да → "Добро пожаловать" + кнопки выбора устройства (VpnAction.NEW)
  └─ Нет → "У вас N устройств" + кнопки [Ошибка VPN, Список, Поддержка]
```

**Вызовы**: `UserInteractor.get_or_create`, `UserView.get_device_count`

---

## Flow 2: `/start {referral_code}` — реферальный вход

**Router**: `src/apps/user/controllers/bot/router.py`

```
/start abc123 → get_or_create(telegram_id, referral_code)
  ├─ ReferralNotFound → "Ошибка реферального кода"
  ├─ free_months == True → "Вы уже использовали бесплатный месяц"
  └─ OK → "Бесплатный месяц" + кнопки выбора устройства (VpnAction.REFERRAL, referral_id)
```

**Вызовы**: `UserInteractor.get_or_create`, `UserGateway.get_by_referral_code`

---

## Flow 3: Покупка VPN (`NEW_SUB`)

**Router**: `src/apps/device/controllers/bot/router.py`, хендлер `handle_vpn_flow`

Весь flow управляется через `VpnCallback` — каждый шаг добавляет поля в callback:

```
Шаг 1: Выбор устройства
  callback: vpn:action=new:device=None → показать кнопки типов (iOS/Android/TV/Windows/MacOS)

Шаг 2: Выбор тарифа
  callback: vpn:action=new:device=iOS:duration=0 → показать кнопки тарифов

Шаг 3: Показ суммы
  callback: vpn:...:duration=3:balance=None → расчёт:
    finally_payment = max(price - user_balance, 0)
    new_balance = max(user_balance - price, 0)
    → показать "Итого к оплате" + [Да/Нет]

Шаг 4: Отмена
  callback: ...:choice=no или payment_status=failed → "Отменено"

Шаг 5: Подтверждение → Проверка email
  callback: ...:choice=yes →
    ├─ email == None → FSM: EmailInput.waiting_for_email → ввод email / "Пропустить"
    └─ email есть → показать QR-код оплаты

Шаг 6: Оплата подтверждена
  callback: ...:payment_status=success →
    create_device(telegram_id, device_type, period_months, amount)
    → deduct_balance (если balance > 0)
    → уведомление админу (ADMIN_ID)
    → "Оплата прошла успешно"
```

**Вызовы**: `UserView.get_balance`, `UserView.get_email`, `UserInteractor.set_email`, `DeviceInteractor.create_device`, `UserInteractor.deduct_balance`

---

## Flow 4: Продление подписки (`RENEW`)

**Router**: `src/apps/device/controllers/bot/router.py`

```
Детали устройства → кнопка "Продлить" → VpnCallback(action=renew, device_name=...) →
  Шаги 2-5 аналогичны Flow 3, но на шаге 6:
    renew_subscription(device_name, period_months, amount)
    → deduct_balance
    → уведомление админу
```

**Вызовы**: `DeviceInteractor.renew_subscription`, `UserInteractor.deduct_balance`

---

## Flow 5: Реферальный бесплатный период (`REFERRAL`)

**Router**: `src/apps/device/controllers/bot/router.py`

```
Из Flow 2 → выбор устройства → выбор тарифа →
  create_device_free(telegram_id, device_type, period_days=free_month)
  → mark_free_month_used(telegram_id)
  → уведомление админу
  → add_referral_bonus(referrer_telegram_id, amount=50)
  → уведомление рефереру
```

**Вызовы**: `DeviceInteractor.create_device_free`, `UserInteractor.mark_free_month_used`, `UserInteractor.add_referral_bonus`

---

## Flow 6: `/devices` — список устройств

**Router**: `src/apps/device/controllers/bot/router.py`

```
/devices или callback "list_devices" →
  list_for_user(telegram_id) → показать кнопки устройств
    → callback "conf:{device_id}" → get_full_info(device_id) → детали + кнопки [Продлить, Удалить]
```

**Вызовы**: `DeviceView.list_for_user`, `DeviceView.get_full_info`

---

## Flow 7: Удаление устройства

**Router**: `src/apps/device/controllers/bot/router.py`

```
callback "del" → список устройств для удаления
  → callback "appr_del_device:{device_id}" → delete_device(device_id)
    → "Устройство удалено"
    → уведомление админу
```

**Вызовы**: `DeviceInteractor.delete_device`

---

## Flow 8: `/help` — помощь

**Router**: `src/common/bot/router.py`

```
/help или callback "support_help" → текст помощи + кнопки настроек:
  → callback "settings:android_phone" → инструкция Android
  → callback "settings:ios" → инструкция iOS
  → callback "settings:desktop" → инструкция Desktop
```

---

## Flow 9: `/web` — вход на сайт

**Router**: `src/apps/user/controllers/bot/router.py`

```
/web → get_user_id(telegram_id) → create_bot_token(user_id)
  → ссылка: {site_url}/api/v1/auth/bot-token/{token}
  → "Ссылка действительна N минут"
```

**Вызовы**: `UserView.get_user_id`, `AuthInteractor.create_bot_token`

---

## Flow 10: `/invite` — реферальная система

**Router**: `src/apps/user/controllers/bot/router.py`

```
/invite → get_referral_code(telegram_id) → показать код и ссылку
```

**Вызовы**: `UserInteractor.get_referral_code`

---

## Flow 11: Сообщение об ошибке VPN

**Router**: `src/common/bot/router.py`

```
callback "vpn_error" → list_for_user(telegram_id) → список устройств
  → callback "report:device_error:{device_id}" → отправка репорта админу
```

**Вызовы**: `DeviceView.list_for_user`

---

## Роутеры и подключение

| Роутер | Файл | Хендлеры |
|--------|------|----------|
| User Bot | `src/apps/user/controllers/bot/router.py` | /start, /start ref, /web, /invite, callback start/cancel |
| Device Bot | `src/apps/device/controllers/bot/router.py` | /devices, VpnCallback flow, delete, detail, email input |
| Common Bot | `src/common/bot/router.py` | /help, vpn_error, device_error report, settings |

Порядок подключения в `main_bot.py`:
1. `user_router`
2. `device_router`
3. `common_router`

Админ ID: `app_config.bot.admin_id` — получает все уведомления о покупках, удалениях, ошибках.
