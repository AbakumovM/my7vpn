# User Domain

**Директория:** `src/apps/user/`

---

## Модель (domain/models.py)

```python
@dataclass
class User:
    telegram_id: int | None = None
    email: str | None = None
    balance: int = 0              # бонусный баланс в рублях
    free_months: bool = False     # использован ли бесплатный период
    referral_code: str | None = None  # MD5[:8] от telegram_id
    referred_by: int | None = None    # telegram_id рефереры
    remnawave_uuid: str | None = None # UUID в панели Remnawave
    subscription_url: str | None = None  # ссылка подписки (из Remnawave)
    web_key: str | None = None    # UUID для входа в личный кабинет
    created_at: date = field(default_factory=date.today)
```

---

## ORM (adapters/orm.py)

**Таблица:** `users`

| Поле | Тип | Особенности |
|------|-----|------------|
| `id` | Integer PK | autoincrement |
| `telegram_id` | BigInteger | UNIQUE, nullable |
| `email` | String | UNIQUE, nullable |
| `created_at` | Date | |
| `referral_code` | String | nullable |
| `referred_by` | BigInteger | telegram_id рефереры |
| `remnawave_uuid` | String(36) | nullable |
| `subscription_url` | String | nullable |
| `web_key` | String(36) | UNIQUE, nullable |
| `balance` | Integer | default=0 |
| `free_months` | Boolean | default=False |
| `devices` | relationship | → DeviceORM (legacy) |

---

## UserInteractor (application/interactor.py)

| Метод | Команда | Что делает |
|-------|---------|-----------|
| `get_or_create()` | `GetOrCreateUser(telegram_id, referred_by_code=None)` | Создать или получить пользователя |
| `get_referral_code()` | `GetReferralCode(telegram_id)` | Вернуть или сгенерировать реф-код (MD5[:8]) |
| `add_referral_bonus()` | `AddReferralBonus(referrer_telegram_id, amount=50)` | Добавить к балансу |
| `deduct_balance()` | `DeductUserBalance(telegram_id, amount)` | Списать с баланса |
| `mark_free_month_used()` | `MarkFreeMonthUsed(telegram_id)` | Установить `free_months=True` |
| `set_email()` | `SetUserEmail(telegram_id, email)` | Сохранить email |
| `get_or_create_web_key()` | — | Создать UUID для кабинета если нет |

**Возвращает:** `UserInfo` (frozen dataclass)

---

## UserView (application/interfaces/view.py)

Только чтение. Инжектируется в **контроллеры**, никогда в Interactor.

| Метод | Возвращает |
|-------|-----------|
| `get_balance(telegram_id)` | `int` |
| `get_user_id(telegram_id)` | `int \| None` — внутренний id |
| `get_telegram_id(user_id)` | `int \| None` |
| `get_email(telegram_id)` | `str \| None` |
| `get_referral_code(telegram_id)` | `str \| None` |
| `get_referral_stats(telegram_id)` | `ReferralStats(invited_count, total_earned, balance)` |
| `get_referrer_telegram_id(referral_code)` | `int \| None` |
| `get_remnawave_uuid(telegram_id)` | `str \| None` |
| `get_device_count(telegram_id)` | `int` |

---

## UserGateway (application/interfaces/gateway.py)

Только запись/чтение для Interactor.

| Метод | Возвращает |
|-------|-----------|
| `get_by_telegram_id(telegram_id)` | `User \| None` |
| `get_by_email(email)` | `User \| None` |
| `get_by_referral_code(referral_code)` | `User \| None` |
| `get_by_web_key(web_key)` | `User \| None` |
| `save(user)` | `None` |

---

## Команды (domain/commands.py)

```python
GetOrCreateUser(telegram_id: int, referred_by_code: str | None = None)
GetReferralCode(telegram_id: int)
AddReferralBonus(referrer_telegram_id: int, amount: int = 50)
DeductUserBalance(telegram_id: int, amount: int)
MarkFreeMonthUsed(telegram_id: int)
SetUserEmail(telegram_id: int, email: str)
```

---

## DI (ioc.py)

`UserProvider` регистрирует:
- `UserInteractor` — REQUEST scope
- Реализации `UserGateway` и `UserView` — REQUEST scope
