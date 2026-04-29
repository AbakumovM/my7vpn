# Device Domain

**Директория:** `src/apps/device/`

Домен включает: Device (legacy), Subscription (legacy), UserSubscription (новая), Payment, PendingPayment.

---

## Модели (domain/models.py)

### UserSubscription (основная, новая)
```python
@dataclass
class UserSubscription:
    user_telegram_id: int
    plan: int          # месяцы (обычно) или дни (реферал/миграция)
    start_date: datetime
    end_date: datetime
    device_limit: int = 1
    is_active: bool = True
    id: int | None = None
```

### UserPayment (основная, новая)
```python
@dataclass
class UserPayment:
    user_telegram_id: int
    amount: int
    duration: int      # месяцев или дней
    device_limit: int
    subscription_id: int | None = None
    payment_date: datetime = ...
    currency: str = "RUB"
    payment_method: str = "карта"  # "карта" | "реферал" | "migration" | "bonus"
    status: str = "success"
    external_id: str | None = None
    id: int | None = None
```

### PendingPayment (ожидание оплаты)
```python
@dataclass
class PendingPayment:
    user_telegram_id: int
    action: str           # "new" | "renew"
    device_type: str      # "vpn"
    duration: int         # месяцев
    amount: int           # к оплате через провайдер (0 = бонусная оплата)
    balance_to_deduct: int
    device_limit: int = 1
    device_name: str | None = None
    created_at: datetime = ...
    id: int | None = None
```

### Device (legacy)
```python
@dataclass
class Device:
    user_id: int           # внутренний id (не telegram_id)
    device_name: str
    created_at: datetime
    vpn_config: str | None = None
    vpn_client_uuid: str | None = None
    device_limit: int = 1
    id: int | None = None
    subscription: Subscription | None = None
```

---

## ORM (adapters/orm.py)

### Новые таблицы

**user_subscriptions:**
| Поле | Тип |
|------|-----|
| id | PK |
| user_id | FK → users.id CASCADE |
| plan | Integer (месяцы или дни) |
| start_date | DateTime TZ |
| end_date | DateTime TZ |
| device_limit | Integer default=1 |
| is_active | Boolean default=True |

**user_payments:**
| Поле | Тип |
|------|-----|
| id | PK |
| user_telegram_id | BigInteger (INDEX) |
| subscription_id | FK → user_subscriptions.id SET NULL |
| amount | Integer |
| duration | Integer |
| device_limit | Integer default=1 |
| payment_date | DateTime TZ |
| currency | String default="RUB" |
| payment_method | String default="карта" |
| status | String(20) default="success" |
| external_id | String nullable |

**pending_payments:**
| Поле | Тип |
|------|-----|
| id | PK autoincrement |
| user_telegram_id | BigInteger |
| action | String(10) |
| device_type | String(20) |
| device_name | String(100) nullable |
| duration | Integer |
| amount | Integer |
| balance_to_deduct | Integer default=0 |
| device_limit | Integer default=1 |
| created_at | DateTime TZ |

### Legacy таблицы (devices, subscriptions, payments)

Используются для хранения старых данных и при миграции (`get_active_subscription_end_date`). Новые подписки создаются только в `user_subscriptions`.

---

## DeviceInteractor (application/interactor.py)

| Метод | Команда | Что делает |
|-------|---------|-----------|
| `create_device_free()` | `CreateDeviceFree` | Реферальный бесплатный период |
| `create_pending_payment()` | `CreatePendingPayment` | Создать запись ожидания оплаты |
| `confirm_payment()` | `ConfirmPayment(pending_id)` | Подтвердить, создать подписку |
| `reject_payment()` | `RejectPayment(pending_id)` | Отклонить, уведомить |
| `migrate_user_to_remnawave()` | `MigrateUser(telegram_id)` | Мигрировать на Remnawave |
| `create_device()` | `CreateDevice` | (устаревший путь) |
| `renew_subscription()` | `RenewSubscription` | (устаревший путь) |
| `delete_device()` | `DeleteDevice` | Удалить устройство |

---

## DeviceView (application/interfaces/view.py)

Только чтение. Инжектируется в контроллеры.

| Метод | Возвращает |
|-------|-----------|
| `get_subscription_info(telegram_id)` | `SubscriptionInfo \| None` |
| `list_for_user(telegram_id)` | `list[DeviceSummary]` |
| `list_for_user_by_id(user_id)` | `list[DeviceSummary]` |
| `get_full_info(device_id)` | `DeviceDetailInfo \| None` |

**SubscriptionInfo:**
```python
SubscriptionInfo:
    end_date: datetime
    device_limit: int
    last_payment_amount: int | None
    subscription_url: str | None
```

---

## DeviceGateway / SubscriptionGateway (application/interfaces/)

**DeviceGateway (legacy):**
- `get_by_id(device_id)`, `get_by_name(device_name)`
- `get_active_by_telegram_id(telegram_id)`
- `get_active_subscription_end_date(telegram_id)` — используется при миграции
- `save(device)`, `delete(device)`, `get_next_seq()`

**SubscriptionGateway (новая):**
- `get_active_by_telegram_id(telegram_id)` → `UserSubscription | None`
- `save(sub)` → `UserSubscription`
- `save_payment(payment)` → `UserPayment`
- `count_payments_for_user(telegram_id)` → `int` — только платные (amount > 0)

---

## Команды (domain/commands.py)

```python
CreatePendingPayment(user_telegram_id, action, device_type, duration, amount,
                     balance_to_deduct=0, device_limit=1, device_name=None)
ConfirmPayment(pending_id: int)
RejectPayment(pending_id: int)
CreateDeviceFree(telegram_id, device_type, period_days, device_limit=1)
MigrateUser(telegram_id: int)
CreateDevice(telegram_id, device_type, period_months, amount, balance_to_deduct=0, device_limit=1)
RenewSubscription(device_name, period_months, amount, balance_to_deduct=0, device_limit=1)
DeleteDevice(device_id: int)
```
