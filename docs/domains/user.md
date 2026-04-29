# User

Управление пользователями: регистрация, баланс, реферальная система, email.

## Модели

### `User` (`domain/models.py`)

| Поле | Тип | Описание |
|------|-----|----------|
| `telegram_id` | `int \| None` | Telegram ID (основной идентификатор) |
| `email` | `str \| None` | Email пользователя |
| `balance` | `int` | Баланс (рубли), default = 0 |
| `free_months` | `bool` | Использован ли бесплатный месяц |
| `referral_code` | `str \| None` | Уникальный реферальный код |
| `referred_by` | `int \| None` | telegram_id реферера |
| `created_at` | `date` | Дата создания |

## Commands (`domain/commands.py`)

| Команда | Поля | Назначение |
|---------|------|------------|
| `GetOrCreateUser` | `telegram_id`, `referred_by_code?` | Найти или создать пользователя |
| `GetReferralCode` | `telegram_id` | Получить/сгенерировать реферальный код |
| `AddReferralBonus` | `referrer_telegram_id`, `amount=50` | Начислить бонус рефереру |
| `DeductUserBalance` | `telegram_id`, `amount` | Списать с баланса |
| `MarkFreeMonthUsed` | `telegram_id` | Пометить бесплатный месяц использованным |
| `SetUserEmail` | `telegram_id`, `email` | Установить email |

## Exceptions (`domain/exceptions.py`)

| Исключение | Параметры | Когда |
|------------|-----------|-------|
| `UserNotFound` | `telegram_id` | Пользователь не найден |
| `ReferralNotFound` | `referral_code` | Реферальный код не найден |
| `InsufficientBalance` | `telegram_id`, `balance`, `required` | Недостаточно средств |

## Interactor (`application/interactor.py`)

`UserInteractor(gateway: UserGateway, uow: SQLAlchemyUoW)`

| Метод | Команда | Возвращает | Логика |
|-------|---------|------------|--------|
| `get_or_create` | `GetOrCreateUser` | `UserInfo` | Если юзер есть — возвращает. Если нет — создаёт, привязывает реферера |
| `get_referral_code` | `GetReferralCode` | `ReferralCodeInfo` | Генерирует md5-код при первом обращении |
| `add_referral_bonus` | `AddReferralBonus` | `UserInfo` | `balance += amount` |
| `deduct_balance` | `DeductUserBalance` | `UserInfo` | `balance -= amount`, проверка InsufficientBalance |
| `mark_free_month_used` | `MarkFreeMonthUsed` | `UserInfo` | `free_months = True` |
| `set_email` | `SetUserEmail` | `UserInfo` | Устанавливает email |

## Gateway — запись (`application/interfaces/gateway.py`)

`UserGateway(Protocol)`

| Метод | Сигнатура |
|-------|-----------|
| `get_by_telegram_id` | `(telegram_id: int) -> User \| None` |
| `get_by_email` | `(email: str) -> User \| None` |
| `get_by_referral_code` | `(referral_code: str) -> User \| None` |
| `save` | `(user: User) -> None` |

## View — чтение (`application/interfaces/view.py`)

`UserView(Protocol)`

| Метод | Сигнатура | Используется |
|-------|-----------|--------------|
| `get_balance` | `(telegram_id: int) -> int` | Bot: расчёт оплаты |
| `get_referral_code` | `(telegram_id: int) -> str \| None` | — |
| `get_device_count` | `(telegram_id: int) -> int` | Bot: /start, /invite |
| `get_email` | `(telegram_id: int) -> str \| None` | Bot: проверка перед оплатой |
| `get_user_id` | `(telegram_id: int) -> int \| None` | HTTP: маппинг tg→db id |
| `get_telegram_id` | `(user_id: int) -> int \| None` | HTTP: маппинг db→tg id |

## Info-объекты (результаты)

| Объект | Поля |
|--------|------|
| `UserInfo` | `telegram_id`, `email`, `balance`, `free_months`, `referral_code` |
| `ReferralCodeInfo` | `telegram_id`, `referral_code` |

## Зависимости от других доменов

Нет. User — корневой домен. Другие домены зависят от User.

## Кто зависит от User

- **Device**: `DeviceInteractor` использует `UserGateway` для проверки пользователя
- **Auth**: `AuthInteractor` использует `UserGateway` для создания/поиска по email

## Файлы

| Файл | Путь |
|------|------|
| Модель | `src/apps/user/domain/models.py` |
| Команды | `src/apps/user/domain/commands.py` |
| Исключения | `src/apps/user/domain/exceptions.py` |
| Interactor | `src/apps/user/application/interactor.py` |
| Gateway (interface) | `src/apps/user/application/interfaces/gateway.py` |
| View (interface) | `src/apps/user/application/interfaces/view.py` |
| ORM | `src/apps/user/adapters/orm.py` |
| Gateway (impl) | `src/apps/user/adapters/gateway.py` |
| View (impl) | `src/apps/user/adapters/view.py` |
| Bot router | `src/apps/user/controllers/bot/router.py` |
| HTTP router | `src/apps/user/controllers/http/router.py` |
| DI provider | `src/apps/user/ioc.py` |
