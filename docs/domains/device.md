# Device (+ Subscription + Payment)

Управление VPN-устройствами, подписками и платежами. Subscription и Payment живут внутри Device как связанные сущности, без собственных Interactor'ов.

## Модели

### `Device` (`domain/models.py`)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `int \| None` | PK (заполняется после save) |
| `user_id` | `int` | telegram_id владельца |
| `device_name` | `str` | Автосгенерированное имя (`"{type} {seq}{rand}"`) |
| `created_at` | `datetime` | Время создания |
| `vpn_config` | `str \| None` | VPN-конфигурация |
| `subscription` | `Subscription \| None` | Связанная подписка |

### `Subscription` (`domain/models.py`)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `int \| None` | PK |
| `device_id` | `int` | FK на Device |
| `plan` | `int` | Срок (месяцы или дни для free) |
| `start_date` | `datetime` | Начало |
| `end_date` | `datetime` | Окончание |
| `is_active` | `bool` | Активна ли (default True) |

### `Payment` (`domain/models.py`)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `int \| None` | PK |
| `subscription_id` | `int` | FK на Subscription |
| `amount` | `int` | Сумма |
| `payment_date` | `datetime` | Дата оплаты |
| `currency` | `str` | Валюта (default `"RUB"`) |
| `payment_method` | `str` | Способ оплаты (default `"карта"`) |

## Commands (`domain/commands.py`)

| Команда | Поля | Назначение |
|---------|------|------------|
| `CreateDevice` | `telegram_id`, `device_type`, `period_months`, `amount` | Создать устройство с подпиской и платежом |
| `CreateDeviceFree` | `telegram_id`, `device_type`, `period_days` | Создать бесплатное устройство (реферал) |
| `DeleteDevice` | `device_id` | Удалить устройство |
| `RenewSubscription` | `device_name`, `period_months`, `amount` | Продлить подписку |
| `GetExpiringSubscriptions` | — | (не используется, см. DeviceView) |

## Exceptions (`domain/exceptions.py`)

| Исключение | Параметры | Когда |
|------------|-----------|-------|
| `DeviceNotFound` | `device_id?`, `device_name?` | Устройство не найдено |
| `SubscriptionNotFound` | `device_id` | У устройства нет подписки |
| `UserDeviceNotFound` | `telegram_id` | Пользователь не найден (при создании устройства) |

## Interactor (`application/interactor.py`)

`DeviceInteractor(gateway: DeviceGateway, user_gateway: UserGateway, uow: SQLAlchemyUoW)`

| Метод | Команда | Возвращает | Логика |
|-------|---------|------------|--------|
| `create_device` | `CreateDevice` | `DeviceCreatedInfo` | Проверяет юзера → генерирует имя → создаёт Device+Subscription+Payment |
| `create_device_free` | `CreateDeviceFree` | `DeviceCreatedInfo` | То же, но `amount=0`, срок в днях |
| `delete_device` | `DeleteDevice` | `str` (device_name) | Находит и удаляет устройство |
| `renew_subscription` | `RenewSubscription` | `SubscriptionInfo` | Продлевает от end_date (если не истекла) или от now |

Генерация имени: `_generate_device_name(device_type)` → `"{type} {seq}{random(1..5000)}"`

## Gateway — запись (`application/interfaces/gateway.py`)

`DeviceGateway(Protocol)`

| Метод | Сигнатура |
|-------|-----------|
| `get_by_id` | `(device_id: int) -> Device \| None` |
| `get_by_name` | `(device_name: str) -> Device \| None` |
| `get_next_seq` | `() -> int` |
| `save` | `(device: Device) -> None` |
| `delete` | `(device: Device) -> None` |

## View — чтение (`application/interfaces/view.py`)

`DeviceView(Protocol)`

| Метод | Сигнатура | Используется |
|-------|-----------|--------------|
| `list_for_user` | `(telegram_id: int) -> list[DeviceSummary]` | Bot: список устройств |
| `list_for_user_by_id` | `(user_id: int) -> list[DeviceSummary]` | HTTP: список устройств |
| `get_full_info` | `(device_id: int) -> DeviceDetailInfo \| None` | Bot + HTTP: детали |
| `get_expiring_today` | `() -> list[ExpiringSubscriptionInfo]` | Scheduler: ежедневная проверка |

## Info-объекты (результаты)

| Объект | Поля | Где определён |
|--------|------|---------------|
| `DeviceCreatedInfo` | `device_name`, `user_telegram_id` | `interactor.py` |
| `SubscriptionInfo` | `device_name`, `end_date`, `plan` | `interactor.py` |
| `DeviceSummary` | `id`, `device_name` | `interfaces/view.py` |
| `DeviceDetailInfo` | `device_name`, `end_date`, `amount`, `payment_date` | `interfaces/view.py` |
| `ExpiringSubscriptionInfo` | `telegram_id`, `device_name`, `plan`, `start_date`, `end_date` | `interfaces/view.py` |

## Зависимости от других доменов

- **User**: `DeviceInteractor` принимает `UserGateway` — проверяет существование пользователя перед созданием устройства

## Файлы

| Файл | Путь |
|------|------|
| Модели | `src/apps/device/domain/models.py` |
| Команды | `src/apps/device/domain/commands.py` |
| Исключения | `src/apps/device/domain/exceptions.py` |
| Interactor | `src/apps/device/application/interactor.py` |
| Gateway (interface) | `src/apps/device/application/interfaces/gateway.py` |
| View (interface) | `src/apps/device/application/interfaces/view.py` |
| ORM | `src/apps/device/adapters/orm.py` |
| Gateway (impl) | `src/apps/device/adapters/gateway.py` |
| View (impl) | `src/apps/device/adapters/view.py` |
| Bot router | `src/apps/device/controllers/bot/router.py` |
| HTTP router | `src/apps/device/controllers/http/router.py` |
| DI provider | `src/apps/device/ioc.py` |
