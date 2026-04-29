# Remnawave API Client — Design Spec

**Date:** 2026-04-20
**Scope:** Infrastructure HTTP-клиент, Gateway Protocol, Adapter, IoC интеграция, тесты
**Stage:** Etap 2 — первый шаг (API layer only, без изменений бот-флоу)

---

## Контекст

Проект мигрирует с 3x-ui на Remnawave. `XuiClient` больше не используется и удаляется в этом этапе. Remnawave уже развёрнут и работает (`panel.zevsgate.com`). Нужно написать типизированный, тестируемый API-клиент и правильно интегрировать его через Gateway Pattern (в отличие от `XuiClient`, который был напрямую в Interactor).

---

## Remnawave API — справочник

**Base URL:** `{panel_url}/api`
**Auth:** `Authorization: Bearer {token}`
**Content-Type:** `application/json`

### Используемые эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/users` | Создать пользователя |
| `PATCH` | `/api/users` | Обновить (expireAt, hwidDeviceLimit, status) |
| `DELETE` | `/api/users/{uuid}` | Удалить пользователя |
| `GET` | `/api/users/by-telegram-id/{id}` | Найти по Telegram ID |
| `POST` | `/api/users/{uuid}/actions/enable` | Включить пользователя |
| `POST` | `/api/users/{uuid}/actions/disable` | Отключить пользователя |

### Create User — `POST /api/users`

**Request:**
```json
{
  "username": "tg123456789",
  "expireAt": "2025-07-17T15:38:45.065Z",
  "hwidDeviceLimit": 3,
  "telegramId": 123456789,
  "trafficLimitBytes": 0
}
```

Правила для `username`: 3–36 символов, только `[a-zA-Z0-9_-]`. Формат: `tg{telegram_id}`.
`trafficLimitBytes: 0` = безлимитный трафик.

**Response `201`:**
```json
{
  "response": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "shortUuid": "Srwsv-4hucr19zGC",
    "username": "tg123456789",
    "status": "ACTIVE",
    "expireAt": "2025-07-17T15:38:45.065Z",
    "subscriptionUrl": "https://sub.zevsgate.com/api/sub/Srwsv-4hucr19zGC",
    "hwidDeviceLimit": 3,
    "telegramId": 123456789,
    "trafficLimitBytes": 0,
    "createdAt": "2025-04-20T10:00:00.000Z",
    "updatedAt": "2025-04-20T10:00:00.000Z"
  }
}
```

### Update User — `PATCH /api/users`

**Request** (uuid или username обязателен):
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "expireAt": "2026-01-17T15:38:45.065Z",
  "hwidDeviceLimit": 5
}
```

`expireAt` не может быть в прошлом. Только те поля, которые нужно изменить.

**Response `200`:** та же структура что и Create.

### Delete User — `DELETE /api/users/{uuid}`

**Response `200`:**
```json
{
  "response": { "isDeleted": true }
}
```

### Get by Telegram ID — `GET /api/users/by-telegram-id/{telegramId}`

**Response `200`:** та же структура что и Create.
**Response `404`:** пользователь не найден.

### Enable / Disable — `POST /api/users/{uuid}/actions/enable|disable`

**Response `200`:** та же структура что и Create (со статусом `ACTIVE` или `DISABLED`).

---

## Архитектура

### Граф зависимостей

```
DeviceInteractor
    └── RemnawaveGateway (Protocol)          ← application/interfaces/
            └── RemnawaveGatewayImpl          ← adapters/
                    └── RemnawaveClient       ← infrastructure/remnawave/
                            └── RemnawaveSettings  ← infrastructure/config.py
```

### Файловая структура

```
src/infrastructure/
├── config.py                               ← добавить RemnawaveSettings
└── remnawave/
    ├── __init__.py
    ├── client.py                           ← HTTP-клиент
    └── models.py                           ← RemnawaveUser (frozen dataclass)

src/apps/device/
├── application/interfaces/
│   └── remnawave_gateway.py               ← RemnawaveGateway (Protocol)
└── adapters/
    └── remnawave_gateway.py               ← RemnawaveGatewayImpl

src/apps/device/ioc.py                     ← регистрация в Dishka
```

**Удаляется:**
```
src/infrastructure/xui/                    ← полностью удаляется
src/apps/device/ioc.py                     ← убрать XuiClient, добавить RemnawaveClient
```

---

## Детальный дизайн

### `RemnawaveSettings` (config.py)

```python
class RemnawaveSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REMNAWAVE_")

    url: str    # REMNAWAVE_URL=https://panel.zevsgate.com
    token: str  # REMNAWAVE_TOKEN=eyJ...
```

Добавляется в `AppConfig` как поле `remnawave: RemnawaveSettings`.

### `RemnawaveUser` (infrastructure/remnawave/models.py)

```python
@dataclass(frozen=True)
class RemnawaveUser:
    uuid: str
    username: str
    subscription_url: str
    expire_at: datetime
    status: str           # "ACTIVE" | "DISABLED" | "LIMITED" | "EXPIRED"
    hwid_device_limit: int | None
    telegram_id: int | None
```

DTO от внешнего API. Frozen — никогда не мутируется после создания.

### `RemnawaveClient` (infrastructure/remnawave/client.py)

- Принимает `RemnawaveSettings` в конструктор
- Создаёт `httpx.AsyncClient` per-request (контекстный менеджер внутри каждого метода) — паттерн как у `XuiClient`
- Заголовок `Authorization: Bearer {token}` добавляется к каждому запросу
- При non-2xx ответе бросает `RemnawaveAPIError(status_code, detail)`
- `get_user_by_telegram_id` возвращает `None` при 404 (не исключение)
- Логирует через `structlog` — `log.info` при успехе, `log.error` при ошибке

```python
class RemnawaveAPIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None: ...

class RemnawaveClient:
    def __init__(self, settings: RemnawaveSettings) -> None: ...

    async def create_user(self, telegram_id: int, expire_at: datetime, device_limit: int) -> RemnawaveUser: ...
    async def update_user(self, uuid: str, expire_at: datetime | None = None, device_limit: int | None = None) -> RemnawaveUser: ...
    async def delete_user(self, uuid: str) -> None: ...
    async def get_user_by_telegram_id(self, telegram_id: int) -> RemnawaveUser | None: ...
    async def enable_user(self, uuid: str) -> None: ...
    async def disable_user(self, uuid: str) -> None: ...
```

### `RemnawaveGateway` (application/interfaces/remnawave_gateway.py)

```python
class RemnawaveGateway(Protocol):
    async def create_user(self, telegram_id: int, expire_at: datetime, device_limit: int) -> RemnawaveUser: ...
    async def update_user(self, uuid: str, expire_at: datetime | None = None, device_limit: int | None = None) -> RemnawaveUser: ...
    async def delete_user(self, uuid: str) -> None: ...
    async def get_user_by_telegram_id(self, telegram_id: int) -> RemnawaveUser | None: ...
    async def enable_user(self, uuid: str) -> None: ...
    async def disable_user(self, uuid: str) -> None: ...
```

Interactor импортирует только этот Protocol. Никакого импорта из `infrastructure`.

### `RemnawaveGatewayImpl` (adapters/remnawave_gateway.py)

```python
class RemnawaveGatewayImpl:
    def __init__(self, client: RemnawaveClient) -> None:
        self._client = client

    # делегирует каждый метод в self._client
```

Тонкий слой делегирования. Сейчас логика == логика клиента. В будущем здесь можно добавить retry, кэширование, маппинг доменных исключений — не трогая клиент.

### IoC (device/ioc.py)

```python
@provide(scope=Scope.APP)
def get_remnawave_client(self, config: AppConfig) -> RemnawaveClient:
    return RemnawaveClient(config.remnawave)   # singleton

@provide
def get_remnawave_gateway(self, client: RemnawaveClient) -> RemnawaveGateway:
    return RemnawaveGatewayImpl(client)         # REQUEST scope
```

`XuiClient` и всё связанное с ним удаляется из `ioc.py`.

---

## Тестирование

**`tests/unit/infrastructure/test_remnawave_client.py`** — тесты `RemnawaveClient` через `respx`:
- `create_user` → корректный `RemnawaveUser`
- `get_user_by_telegram_id` → `None` при 404
- `delete_user` → нет исключений при `isDeleted: true`
- `RemnawaveAPIError` при ответе 500

**`tests/unit/adapters/test_remnawave_gateway.py`** — тесты `RemnawaveGatewayImpl`:
- Мокируем `RemnawaveClient`, проверяем делегирование
- Проверяем что методы Protocol выполняются корректно

**Тесты Interactor** (будущее) — мокируем `RemnawaveGateway` Protocol напрямую.

---

## Что не входит в этот спек

- Изменения бот-флоу (новый флоу покупки, диалоги)
- ORM-поля `remnawave_uuid`, `subscription_url` на модели User
- Новая таблица `UserSubscriptionORM`
- Alembic миграции

Это Etap 2, шаги 2–4. Каждый шаг — отдельный спек.
