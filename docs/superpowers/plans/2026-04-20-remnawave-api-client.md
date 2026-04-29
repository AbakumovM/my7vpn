# Remnawave API Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить `XuiClient` на типизированный `RemnawaveClient` с Gateway-паттерном — инфраструктурный HTTP-клиент, Protocol-интерфейс и адаптер.

**Architecture:** `RemnawaveClient` (infrastructure) → `RemnawaveGatewayImpl` (adapter) → `RemnawaveGateway` Protocol (application/interfaces). Interactor зависит только от Protocol. Тесты на каждом слое независимы.

**Tech Stack:** Python 3.12, httpx, respx (mock), structlog, Dishka, pytest-asyncio

---

## Файловая структура

**Создать:**
- `src/infrastructure/remnawave/__init__.py`
- `src/infrastructure/remnawave/client.py` — `RemnawaveAPIError`, `RemnawaveApiUser`, `RemnawaveClient`
- `src/apps/device/application/interfaces/remnawave_gateway.py` — `RemnawaveUserInfo`, `RemnawaveGateway`
- `src/apps/device/adapters/remnawave_gateway.py` — `RemnawaveGatewayImpl`
- `tests/unit/infrastructure/__init__.py`
- `tests/unit/infrastructure/test_remnawave_client.py`
- `tests/unit/device/test_remnawave_gateway.py`

**Изменить:**
- `pyproject.toml` — добавить `respx`
- `src/infrastructure/config.py` — добавить `RemnawaveSettings`, удалить `XuiSettings`
- `src/apps/device/application/interactor.py` — удалить `xui_client`, упростить `delete_device` и `confirm_payment`
- `src/apps/device/ioc.py` — убрать `XuiClient`, зарегистрировать `RemnawaveClient` + `RemnawaveGateway`
- `tests/unit/device/conftest.py` — убрать `mock_xui_client`, добавить `mock_remnawave_gateway`
- `tests/unit/device/test_device_interactor.py` — обновить `test_confirm_payment_new_*`

**Удалить:**
- `src/infrastructure/xui/` — весь каталог
- `tests/unit/device/test_xui_client.py`

---

## Task 1: Добавить respx в зависимости

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Добавить respx в dev-зависимости**

В `pyproject.toml` найти секцию `[project.optional-dependencies]` и добавить `respx`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "respx>=0.21.0",
]
```

- [ ] **Step 2: Установить зависимости**

```bash
uv sync --extra dev
```

Ожидаемый вывод: строка `+ respx ...` в логе установки.

- [ ] **Step 3: Проверить что respx доступен**

```bash
uv run python -c "import respx; print(respx.__version__)"
```

Ожидаемый вывод: версия вида `0.21.x`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add respx to dev dependencies for httpx mocking"
```

---

## Task 2: RemnawaveSettings — конфиг

**Files:**
- Modify: `src/infrastructure/config.py`

- [ ] **Step 1: Заменить XuiSettings на RemnawaveSettings**

Открыть `src/infrastructure/config.py`. Найти класс `XuiSettings` и весь блок с ним — заменить:

```python
class RemnawaveSettings(BaseModel):
    url: str = ""
    token: str = ""
```

Найти в `AppConfig` поле `xui: XuiSettings = Field(default_factory=XuiSettings)` — заменить:

```python
remnawave: RemnawaveSettings = Field(default_factory=RemnawaveSettings)
```

Итоговый `config.py` (полный файл):

```python
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    url: str


class BotSettings(BaseModel):
    token: str
    bot_name: str
    admin_id: int


class PaymentSettings(BaseModel):
    payment_url: str
    payment_qr: str
    free_month: int


class AuthSettings(BaseModel):
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    otp_expire_minutes: int = 5
    bot_token_expire_minutes: int = 10
    site_url: str = "http://localhost:8000"


class SmtpSettings(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""


class RemnawaveSettings(BaseModel):
    url: str = ""
    token: str = ""


class LoggingSettings(BaseModel):
    log_level: str = "INFO"
    log_json: bool = False
    log_to_file: bool = False
    log_dir: Path = Path("logs")
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5


class AppConfig(BaseSettings):
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    smtp: SmtpSettings = Field(default_factory=SmtpSettings)
    remnawave: RemnawaveSettings = Field(default_factory=RemnawaveSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )


app_config = AppConfig()
```

Env-переменные для Remnawave: `REMNAWAVE__URL` и `REMNAWAVE__TOKEN`.

- [ ] **Step 2: Проверить что конфиг загружается без ошибок**

```bash
uv run python -c "from src.infrastructure.config import AppConfig; c = AppConfig(); print(c.remnawave)"
```

Ожидаемый вывод: `url='' token=''` (пустые значения по умолчанию).

- [ ] **Step 3: Commit**

```bash
git add src/infrastructure/config.py
git commit -m "refactor: replace XuiSettings with RemnawaveSettings in config"
```

---

## Task 3: RemnawaveApiUser и RemnawaveClient — create_user (TDD)

**Files:**
- Create: `src/infrastructure/remnawave/__init__.py`
- Create: `src/infrastructure/remnawave/client.py`
- Create: `tests/unit/infrastructure/__init__.py`
- Create: `tests/unit/infrastructure/test_remnawave_client.py`

- [ ] **Step 1: Создать пустые __init__.py**

```bash
touch src/infrastructure/remnawave/__init__.py
touch tests/unit/infrastructure/__init__.py
```

- [ ] **Step 2: Написать failing-тест для create_user**

Создать `tests/unit/infrastructure/test_remnawave_client.py`:

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from src.infrastructure.config import RemnawaveSettings
from src.infrastructure.remnawave.client import RemnawaveAPIError, RemnawaveApiUser, RemnawaveClient

BASE_URL = "https://panel.test.com"


def make_settings() -> RemnawaveSettings:
    return RemnawaveSettings(url=BASE_URL, token="test-token-abc")


def make_user_response(
    uuid: str = "550e8400-e29b-41d4-a716-446655440000",
    username: str = "tg123456789",
    subscription_url: str = "https://sub.test.com/api/sub/abc123",
    expire_at: str = "2025-07-17T15:38:45.000Z",
    status: str = "ACTIVE",
    hwid_device_limit: int | None = 3,
    telegram_id: int | None = 123456789,
) -> dict:
    return {
        "response": {
            "uuid": uuid,
            "username": username,
            "subscriptionUrl": subscription_url,
            "expireAt": expire_at,
            "status": status,
            "hwidDeviceLimit": hwid_device_limit,
            "telegramId": telegram_id,
        }
    }


@respx.mock
@pytest.mark.asyncio
async def test_create_user_returns_remnawave_api_user() -> None:
    """create_user отправляет POST /api/users и возвращает RemnawaveApiUser."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    expire_at = datetime(2025, 7, 17, 15, 38, 45, tzinfo=timezone.utc)

    respx.post(f"{BASE_URL}/api/users").mock(
        return_value=httpx.Response(201, json=make_user_response())
    )

    result = await client.create_user(telegram_id=123456789, expire_at=expire_at, device_limit=3)

    assert isinstance(result, RemnawaveApiUser)
    assert result.uuid == "550e8400-e29b-41d4-a716-446655440000"
    assert result.username == "tg123456789"
    assert result.subscription_url == "https://sub.test.com/api/sub/abc123"
    assert result.status == "ACTIVE"
    assert result.hwid_device_limit == 3
    assert result.telegram_id == 123456789


@respx.mock
@pytest.mark.asyncio
async def test_create_user_sends_correct_payload() -> None:
    """create_user отправляет username=tg{id}, trafficLimitBytes=0, hwidDeviceLimit."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    expire_at = datetime(2025, 7, 17, 15, 38, 45, tzinfo=timezone.utc)

    route = respx.post(f"{BASE_URL}/api/users").mock(
        return_value=httpx.Response(201, json=make_user_response())
    )

    await client.create_user(telegram_id=123456789, expire_at=expire_at, device_limit=3)

    sent = route.calls.last.request
    import json
    payload = json.loads(sent.content)
    assert payload["username"] == "tg123456789"
    assert payload["telegramId"] == 123456789
    assert payload["hwidDeviceLimit"] == 3
    assert payload["trafficLimitBytes"] == 0
    assert "expireAt" in payload


@respx.mock
@pytest.mark.asyncio
async def test_create_user_raises_api_error_on_500() -> None:
    """create_user бросает RemnawaveAPIError при ответе 500."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    expire_at = datetime(2025, 7, 17, 15, 38, 45, tzinfo=timezone.utc)

    respx.post(f"{BASE_URL}/api/users").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with pytest.raises(RemnawaveAPIError) as exc_info:
        await client.create_user(telegram_id=123456789, expire_at=expire_at, device_limit=3)

    assert exc_info.value.status_code == 500
```

- [ ] **Step 3: Запустить — убедиться что тест падает**

```bash
uv run pytest tests/unit/infrastructure/test_remnawave_client.py -v
```

Ожидаемый вывод: `ImportError` или `ModuleNotFoundError` — `client.py` ещё не существует.

- [ ] **Step 4: Создать `src/infrastructure/remnawave/client.py`**

```python
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import structlog

from src.infrastructure.config import RemnawaveSettings

log = structlog.get_logger(__name__)


class RemnawaveAPIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Remnawave API error {status_code}: {detail}")


@dataclass
class RemnawaveApiUser:
    uuid: str
    username: str
    subscription_url: str
    expire_at: str   # raw ISO string from API — парсинг в адаптере
    status: str
    hwid_device_limit: int | None
    telegram_id: int | None


class RemnawaveClient:
    def __init__(self, settings: RemnawaveSettings) -> None:
        self._settings = settings

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.token}",
            "Content-Type": "application/json",
        }

    def _parse_user(self, data: dict) -> RemnawaveApiUser:  # type: ignore[type-arg]
        return RemnawaveApiUser(
            uuid=data["uuid"],
            username=data["username"],
            subscription_url=data["subscriptionUrl"],
            expire_at=data["expireAt"],
            status=data["status"],
            hwid_device_limit=data.get("hwidDeviceLimit"),
            telegram_id=data.get("telegramId"),
        )

    async def create_user(
        self,
        telegram_id: int,
        expire_at: datetime,
        device_limit: int,
    ) -> RemnawaveApiUser:
        payload = {
            "username": f"tg{telegram_id}",
            "expireAt": expire_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "hwidDeviceLimit": device_limit,
            "telegramId": telegram_id,
            "trafficLimitBytes": 0,
        }
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.post("/api/users", json=payload, headers=self._headers())
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
            data = resp.json()["response"]
        log.info("remnawave_user_created", telegram_id=telegram_id, uuid=data["uuid"])
        return self._parse_user(data)
```

- [ ] **Step 5: Запустить — убедиться что тесты проходят**

```bash
uv run pytest tests/unit/infrastructure/test_remnawave_client.py -v
```

Ожидаемый вывод: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/remnawave/ tests/unit/infrastructure/
git commit -m "feat: add RemnawaveClient with create_user (TDD)"
```

---

## Task 4: RemnawaveClient — остальные методы (TDD)

**Files:**
- Modify: `tests/unit/infrastructure/test_remnawave_client.py`
- Modify: `src/infrastructure/remnawave/client.py`

- [ ] **Step 1: Добавить тесты для remaining методов**

Дописать в конец `tests/unit/infrastructure/test_remnawave_client.py`:

```python
@respx.mock
@pytest.mark.asyncio
async def test_update_user_sends_patch_with_uuid() -> None:
    """update_user отправляет PATCH /api/users с uuid и expireAt."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    expire_at = datetime(2026, 1, 17, 15, 38, 45, tzinfo=timezone.utc)

    respx.patch(f"{BASE_URL}/api/users").mock(
        return_value=httpx.Response(200, json=make_user_response(
            expire_at="2026-01-17T15:38:45.000Z"
        ))
    )

    result = await client.update_user(
        uuid="550e8400-e29b-41d4-a716-446655440000",
        expire_at=expire_at,
    )

    assert result.uuid == "550e8400-e29b-41d4-a716-446655440000"


@respx.mock
@pytest.mark.asyncio
async def test_update_user_sends_only_provided_fields() -> None:
    """update_user не включает None-поля в payload."""
    settings = make_settings()
    client = RemnawaveClient(settings)

    route = respx.patch(f"{BASE_URL}/api/users").mock(
        return_value=httpx.Response(200, json=make_user_response())
    )

    await client.update_user(uuid="test-uuid", device_limit=5)

    import json
    payload = json.loads(route.calls.last.request.content)
    assert payload["uuid"] == "test-uuid"
    assert payload["hwidDeviceLimit"] == 5
    assert "expireAt" not in payload


@respx.mock
@pytest.mark.asyncio
async def test_delete_user_sends_delete_request() -> None:
    """delete_user отправляет DELETE /api/users/{uuid} без исключений."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    test_uuid = "550e8400-e29b-41d4-a716-446655440000"

    respx.delete(f"{BASE_URL}/api/users/{test_uuid}").mock(
        return_value=httpx.Response(200, json={"response": {"isDeleted": True}})
    )

    await client.delete_user(test_uuid)  # не должно бросать исключений


@respx.mock
@pytest.mark.asyncio
async def test_delete_user_raises_on_404() -> None:
    """delete_user бросает RemnawaveAPIError при 404."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    test_uuid = "nonexistent-uuid"

    respx.delete(f"{BASE_URL}/api/users/{test_uuid}").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    with pytest.raises(RemnawaveAPIError) as exc_info:
        await client.delete_user(test_uuid)

    assert exc_info.value.status_code == 404


@respx.mock
@pytest.mark.asyncio
async def test_get_user_by_telegram_id_returns_user() -> None:
    """get_user_by_telegram_id возвращает RemnawaveApiUser при 200."""
    settings = make_settings()
    client = RemnawaveClient(settings)

    respx.get(f"{BASE_URL}/api/users/by-telegram-id/123456789").mock(
        return_value=httpx.Response(200, json=make_user_response())
    )

    result = await client.get_user_by_telegram_id(123456789)

    assert result is not None
    assert result.uuid == "550e8400-e29b-41d4-a716-446655440000"


@respx.mock
@pytest.mark.asyncio
async def test_get_user_by_telegram_id_returns_none_on_404() -> None:
    """get_user_by_telegram_id возвращает None при 404 (пользователь не найден)."""
    settings = make_settings()
    client = RemnawaveClient(settings)

    respx.get(f"{BASE_URL}/api/users/by-telegram-id/999").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    result = await client.get_user_by_telegram_id(999)

    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_enable_user_sends_post_to_enable_endpoint() -> None:
    """enable_user отправляет POST /api/users/{uuid}/actions/enable."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    test_uuid = "550e8400-e29b-41d4-a716-446655440000"

    respx.post(f"{BASE_URL}/api/users/{test_uuid}/actions/enable").mock(
        return_value=httpx.Response(200, json=make_user_response(status="ACTIVE"))
    )

    await client.enable_user(test_uuid)  # не должно бросать исключений


@respx.mock
@pytest.mark.asyncio
async def test_disable_user_sends_post_to_disable_endpoint() -> None:
    """disable_user отправляет POST /api/users/{uuid}/actions/disable."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    test_uuid = "550e8400-e29b-41d4-a716-446655440000"

    respx.post(f"{BASE_URL}/api/users/{test_uuid}/actions/disable").mock(
        return_value=httpx.Response(200, json=make_user_response(status="DISABLED"))
    )

    await client.disable_user(test_uuid)  # не должно бросать исключений
```

- [ ] **Step 2: Запустить — убедиться что новые тесты падают**

```bash
uv run pytest tests/unit/infrastructure/test_remnawave_client.py -v
```

Ожидаемый вывод: `3 passed, 8 failed` — старые проходят, новые падают с `AttributeError`.

- [ ] **Step 3: Дописать оставшиеся методы в `client.py`**

Добавить в класс `RemnawaveClient` после `create_user`:

```python
    async def update_user(
        self,
        uuid: str,
        expire_at: datetime | None = None,
        device_limit: int | None = None,
    ) -> RemnawaveApiUser:
        payload: dict[str, object] = {"uuid": uuid}
        if expire_at is not None:
            payload["expireAt"] = expire_at.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            )
        if device_limit is not None:
            payload["hwidDeviceLimit"] = device_limit
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.patch("/api/users", json=payload, headers=self._headers())
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
            data = resp.json()["response"]
        log.info("remnawave_user_updated", uuid=uuid)
        return self._parse_user(data)

    async def delete_user(self, uuid: str) -> None:
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.delete(f"/api/users/{uuid}", headers=self._headers())
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
        log.info("remnawave_user_deleted", uuid=uuid)

    async def get_user_by_telegram_id(self, telegram_id: int) -> RemnawaveApiUser | None:
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.get(
                f"/api/users/by-telegram-id/{telegram_id}", headers=self._headers()
            )
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
            data = resp.json()["response"]
        return self._parse_user(data)

    async def enable_user(self, uuid: str) -> None:
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.post(
                f"/api/users/{uuid}/actions/enable", headers=self._headers()
            )
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
        log.info("remnawave_user_enabled", uuid=uuid)

    async def disable_user(self, uuid: str) -> None:
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.post(
                f"/api/users/{uuid}/actions/disable", headers=self._headers()
            )
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
        log.info("remnawave_user_disabled", uuid=uuid)
```

- [ ] **Step 4: Запустить — все тесты должны пройти**

```bash
uv run pytest tests/unit/infrastructure/test_remnawave_client.py -v
```

Ожидаемый вывод: `11 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/remnawave/client.py tests/unit/infrastructure/test_remnawave_client.py
git commit -m "feat: add remaining RemnawaveClient methods with tests"
```

---

## Task 5: RemnawaveUserInfo + RemnawaveGateway Protocol

**Files:**
- Create: `src/apps/device/application/interfaces/remnawave_gateway.py`

- [ ] **Step 1: Создать файл Protocol**

Создать `src/apps/device/application/interfaces/remnawave_gateway.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RemnawaveUserInfo:
    uuid: str
    username: str
    subscription_url: str
    expire_at: datetime
    status: str           # "ACTIVE" | "DISABLED" | "LIMITED" | "EXPIRED"
    hwid_device_limit: int | None
    telegram_id: int | None


class RemnawaveGateway(Protocol):
    async def create_user(
        self, telegram_id: int, expire_at: datetime, device_limit: int
    ) -> RemnawaveUserInfo: ...

    async def update_user(
        self,
        uuid: str,
        expire_at: datetime | None = None,
        device_limit: int | None = None,
    ) -> RemnawaveUserInfo: ...

    async def delete_user(self, uuid: str) -> None: ...

    async def get_user_by_telegram_id(
        self, telegram_id: int
    ) -> RemnawaveUserInfo | None: ...

    async def enable_user(self, uuid: str) -> None: ...

    async def disable_user(self, uuid: str) -> None: ...
```

- [ ] **Step 2: Проверить импорт**

```bash
uv run python -c "from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway, RemnawaveUserInfo; print('OK')"
```

Ожидаемый вывод: `OK`.

- [ ] **Step 3: Commit**

```bash
git add src/apps/device/application/interfaces/remnawave_gateway.py
git commit -m "feat: add RemnawaveGateway Protocol and RemnawaveUserInfo"
```

---

## Task 6: RemnawaveGatewayImpl — адаптер (TDD)

**Files:**
- Create: `tests/unit/device/test_remnawave_gateway.py`
- Create: `src/apps/device/adapters/remnawave_gateway.py`

- [ ] **Step 1: Написать failing-тесты для адаптера**

Создать `tests/unit/device/test_remnawave_gateway.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.apps.device.adapters.remnawave_gateway import RemnawaveGatewayImpl
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveUserInfo
from src.infrastructure.remnawave.client import RemnawaveApiUser, RemnawaveAPIError


pytestmark = pytest.mark.asyncio


def make_api_user(
    uuid: str = "test-uuid-1234",
    username: str = "tg111",
    subscription_url: str = "https://sub.test.com/api/sub/abc",
    expire_at: str = "2025-07-17T15:38:45.000Z",
    status: str = "ACTIVE",
    hwid_device_limit: int | None = 3,
    telegram_id: int | None = 111,
) -> RemnawaveApiUser:
    return RemnawaveApiUser(
        uuid=uuid,
        username=username,
        subscription_url=subscription_url,
        expire_at=expire_at,
        status=status,
        hwid_device_limit=hwid_device_limit,
        telegram_id=telegram_id,
    )


async def test_create_user_maps_api_user_to_user_info() -> None:
    """create_user делегирует клиенту и маппит RemnawaveApiUser → RemnawaveUserInfo."""
    mock_client = AsyncMock()
    mock_client.create_user.return_value = make_api_user()
    gateway = RemnawaveGatewayImpl(mock_client)

    expire_at = datetime(2025, 7, 17, 15, 38, 45, tzinfo=timezone.utc)
    result = await gateway.create_user(telegram_id=111, expire_at=expire_at, device_limit=3)

    assert isinstance(result, RemnawaveUserInfo)
    assert result.uuid == "test-uuid-1234"
    assert result.username == "tg111"
    assert result.subscription_url == "https://sub.test.com/api/sub/abc"
    assert isinstance(result.expire_at, datetime)
    assert result.status == "ACTIVE"
    assert result.hwid_device_limit == 3
    assert result.telegram_id == 111
    mock_client.create_user.assert_called_once_with(
        telegram_id=111, expire_at=expire_at, device_limit=3
    )


async def test_create_user_expire_at_is_parsed_to_datetime() -> None:
    """expire_at из строки API корректно парсится в datetime с timezone."""
    mock_client = AsyncMock()
    mock_client.create_user.return_value = make_api_user(
        expire_at="2025-07-17T15:38:45.000Z"
    )
    gateway = RemnawaveGatewayImpl(mock_client)

    expire_at = datetime(2025, 7, 17, tzinfo=timezone.utc)
    result = await gateway.create_user(telegram_id=111, expire_at=expire_at, device_limit=1)

    assert result.expire_at.tzinfo is not None
    assert result.expire_at.year == 2025
    assert result.expire_at.month == 7
    assert result.expire_at.day == 17


async def test_update_user_delegates_to_client() -> None:
    """update_user делегирует клиенту и возвращает RemnawaveUserInfo."""
    mock_client = AsyncMock()
    mock_client.update_user.return_value = make_api_user(uuid="upd-uuid")
    gateway = RemnawaveGatewayImpl(mock_client)

    expire_at = datetime(2026, 1, 17, tzinfo=timezone.utc)
    result = await gateway.update_user(uuid="upd-uuid", expire_at=expire_at)

    assert result.uuid == "upd-uuid"
    mock_client.update_user.assert_called_once_with(
        uuid="upd-uuid", expire_at=expire_at, device_limit=None
    )


async def test_delete_user_delegates_to_client() -> None:
    """delete_user делегирует клиенту и не бросает исключений."""
    mock_client = AsyncMock()
    gateway = RemnawaveGatewayImpl(mock_client)

    await gateway.delete_user("del-uuid")

    mock_client.delete_user.assert_called_once_with("del-uuid")


async def test_get_user_by_telegram_id_returns_none_when_not_found() -> None:
    """get_user_by_telegram_id возвращает None если клиент вернул None."""
    mock_client = AsyncMock()
    mock_client.get_user_by_telegram_id.return_value = None
    gateway = RemnawaveGatewayImpl(mock_client)

    result = await gateway.get_user_by_telegram_id(999)

    assert result is None


async def test_get_user_by_telegram_id_returns_user_info() -> None:
    """get_user_by_telegram_id возвращает RemnawaveUserInfo при найденном пользователе."""
    mock_client = AsyncMock()
    mock_client.get_user_by_telegram_id.return_value = make_api_user(telegram_id=42)
    gateway = RemnawaveGatewayImpl(mock_client)

    result = await gateway.get_user_by_telegram_id(42)

    assert result is not None
    assert result.telegram_id == 42


async def test_enable_user_delegates_to_client() -> None:
    """enable_user делегирует клиенту."""
    mock_client = AsyncMock()
    gateway = RemnawaveGatewayImpl(mock_client)

    await gateway.enable_user("some-uuid")

    mock_client.enable_user.assert_called_once_with("some-uuid")


async def test_disable_user_delegates_to_client() -> None:
    """disable_user делегирует клиенту."""
    mock_client = AsyncMock()
    gateway = RemnawaveGatewayImpl(mock_client)

    await gateway.disable_user("some-uuid")

    mock_client.disable_user.assert_called_once_with("some-uuid")
```

- [ ] **Step 2: Запустить — убедиться что тесты падают**

```bash
uv run pytest tests/unit/device/test_remnawave_gateway.py -v
```

Ожидаемый вывод: `ImportError` — `remnawave_gateway.py` в adapters ещё не создан.

- [ ] **Step 3: Создать `src/apps/device/adapters/remnawave_gateway.py`**

```python
from datetime import datetime

from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveUserInfo
from src.infrastructure.remnawave.client import RemnawaveApiUser, RemnawaveClient


class RemnawaveGatewayImpl:
    def __init__(self, client: RemnawaveClient) -> None:
        self._client = client

    def _map(self, raw: RemnawaveApiUser) -> RemnawaveUserInfo:
        return RemnawaveUserInfo(
            uuid=raw.uuid,
            username=raw.username,
            subscription_url=raw.subscription_url,
            expire_at=datetime.fromisoformat(raw.expire_at.replace("Z", "+00:00")),
            status=raw.status,
            hwid_device_limit=raw.hwid_device_limit,
            telegram_id=raw.telegram_id,
        )

    async def create_user(
        self, telegram_id: int, expire_at: datetime, device_limit: int
    ) -> RemnawaveUserInfo:
        raw = await self._client.create_user(
            telegram_id=telegram_id, expire_at=expire_at, device_limit=device_limit
        )
        return self._map(raw)

    async def update_user(
        self,
        uuid: str,
        expire_at: datetime | None = None,
        device_limit: int | None = None,
    ) -> RemnawaveUserInfo:
        raw = await self._client.update_user(
            uuid=uuid, expire_at=expire_at, device_limit=device_limit
        )
        return self._map(raw)

    async def delete_user(self, uuid: str) -> None:
        await self._client.delete_user(uuid)

    async def get_user_by_telegram_id(
        self, telegram_id: int
    ) -> RemnawaveUserInfo | None:
        raw = await self._client.get_user_by_telegram_id(telegram_id)
        if raw is None:
            return None
        return self._map(raw)

    async def enable_user(self, uuid: str) -> None:
        await self._client.enable_user(uuid)

    async def disable_user(self, uuid: str) -> None:
        await self._client.disable_user(uuid)
```

- [ ] **Step 4: Запустить — все тесты должны пройти**

```bash
uv run pytest tests/unit/device/test_remnawave_gateway.py -v
```

Ожидаемый вывод: `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/apps/device/adapters/remnawave_gateway.py tests/unit/device/test_remnawave_gateway.py
git commit -m "feat: add RemnawaveGatewayImpl adapter with tests"
```

---

## Task 7: Обновить DeviceInteractor — удалить XuiClient

**Files:**
- Modify: `src/apps/device/application/interactor.py`

- [ ] **Step 1: Обновить interactor.py**

Заменить полное содержимое `src/apps/device/application/interactor.py`:

```python
import random
from dataclasses import dataclass
from datetime import UTC, datetime

from dateutil.relativedelta import relativedelta

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.view import ExpiringSubscriptionInfo
from src.apps.device.domain.commands import (
    ConfirmPayment,
    CreateDevice,
    CreateDeviceFree,
    CreatePendingPayment,
    DeleteDevice,
    GetExpiringSubscriptions,
    RejectPayment,
    RenewSubscription,
)
from src.apps.device.domain.exceptions import (
    DeviceNotFound,
    PendingPaymentNotFound,
    SubscriptionNotFound,
    UserDeviceNotFound,
)
from src.apps.device.domain.models import Device, Payment, PendingPayment, Subscription
from src.apps.user.application.interfaces.gateway import UserGateway
from src.apps.user.domain.exceptions import InsufficientBalance
from src.infrastructure.database.uow import SQLAlchemyUoW


@dataclass(frozen=True)
class DeviceCreatedInfo:
    device_name: str
    user_telegram_id: int


@dataclass(frozen=True)
class SubscriptionInfo:
    device_name: str
    end_date: datetime
    plan: int


@dataclass(frozen=True)
class PendingPaymentInfo:
    id: int
    user_telegram_id: int
    action: str
    device_type: str
    device_name: str | None
    duration: int
    amount: int


@dataclass(frozen=True)
class ConfirmPaymentResult:
    user_telegram_id: int
    device_name: str
    action: str              # "new" | "renew"
    vless_link: str | None   # временно None для "new" до интеграции Remnawave
    end_date: datetime | None


class DeviceInteractor:
    def __init__(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        pending_gateway: PendingPaymentGateway,
    ) -> None:
        self._gateway = gateway
        self._user_gateway = user_gateway
        self._uow = uow
        self._pending_gateway = pending_gateway

    async def create_device(self, cmd: CreateDevice) -> DeviceCreatedInfo:
        user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserDeviceNotFound(cmd.telegram_id)

        device_name = await self._generate_device_name(cmd.device_type)
        now = datetime.now(UTC)
        end_date = now + relativedelta(months=cmd.period_months)

        subscription = Subscription(
            device_id=0,
            plan=cmd.period_months,
            start_date=now,
            end_date=end_date,
        )
        payment = Payment(
            subscription_id=0,
            amount=cmd.amount,
            payment_date=now,
        )
        device = Device(
            user_id=user.telegram_id,
            device_name=device_name,
            created_at=now,
            vpn_config=cmd.vpn_config,
            subscription=subscription,
        )
        device.subscription.payments = [payment]  # type: ignore[attr-defined]

        if cmd.balance_to_deduct > 0:
            if user.balance < cmd.balance_to_deduct:
                raise InsufficientBalance(cmd.telegram_id, user.balance, cmd.balance_to_deduct)
            user.balance -= cmd.balance_to_deduct
            await self._user_gateway.save(user)

        await self._gateway.save(device)
        await self._uow.commit()
        return DeviceCreatedInfo(device_name=device_name, user_telegram_id=cmd.telegram_id)

    async def create_device_free(self, cmd: CreateDeviceFree) -> DeviceCreatedInfo:
        user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserDeviceNotFound(cmd.telegram_id)

        device_name = await self._generate_device_name(cmd.device_type)
        now = datetime.now(UTC)
        end_date = now + relativedelta(days=cmd.period_days)

        subscription = Subscription(
            device_id=0,
            plan=cmd.period_days,
            start_date=now,
            end_date=end_date,
        )
        subscription.payments = [Payment(subscription_id=0, amount=0, payment_date=now)]  # type: ignore[attr-defined]
        device = Device(
            user_id=user.telegram_id,
            device_name=device_name,
            created_at=now,
            subscription=subscription,
        )

        await self._gateway.save(device)
        await self._uow.commit()
        return DeviceCreatedInfo(device_name=device_name, user_telegram_id=cmd.telegram_id)

    async def delete_device(self, cmd: DeleteDevice) -> str:
        device = await self._gateway.get_by_id(cmd.device_id)
        if device is None:
            raise DeviceNotFound(device_id=cmd.device_id)
        device_name = device.device_name
        await self._gateway.delete(device)
        await self._uow.commit()
        return device_name

    async def renew_subscription(self, cmd: RenewSubscription) -> SubscriptionInfo:
        device = await self._gateway.get_by_name(cmd.device_name)
        if device is None:
            raise DeviceNotFound(device_name=cmd.device_name)
        if device.subscription is None:
            raise SubscriptionNotFound(device.id or 0)

        now = datetime.now(UTC)
        sub = device.subscription
        base = sub.end_date if sub.end_date > now else now
        sub.end_date = base + relativedelta(months=cmd.period_months)
        sub.plan = cmd.period_months
        sub.start_date = now

        if cmd.balance_to_deduct > 0:
            renewal_user = await self._user_gateway.get_by_telegram_id(device.user_id)
            if renewal_user is None:
                raise UserDeviceNotFound(device.user_id)
            if renewal_user.balance < cmd.balance_to_deduct:
                raise InsufficientBalance(device.user_id, renewal_user.balance, cmd.balance_to_deduct)
            renewal_user.balance -= cmd.balance_to_deduct
            await self._user_gateway.save(renewal_user)

        await self._gateway.save(device)
        await self._uow.commit()
        return SubscriptionInfo(
            device_name=device.device_name,
            end_date=sub.end_date,
            plan=sub.plan,
        )

    async def get_expiring_subscriptions(
        self, cmd: GetExpiringSubscriptions
    ) -> list[ExpiringSubscriptionInfo]:
        raise NotImplementedError("Use DeviceView.get_expiring_today() directly")

    async def create_pending_payment(self, cmd: CreatePendingPayment) -> PendingPaymentInfo:
        now = datetime.now(UTC)
        pending = PendingPayment(
            user_telegram_id=cmd.user_telegram_id,
            action=cmd.action,
            device_type=cmd.device_type,
            device_name=cmd.device_name,
            duration=cmd.duration,
            amount=cmd.amount,
            balance_to_deduct=cmd.balance_to_deduct,
            created_at=now,
        )
        saved = await self._pending_gateway.save(pending)
        await self._uow.commit()
        return PendingPaymentInfo(
            id=saved.id,  # type: ignore[arg-type]
            user_telegram_id=saved.user_telegram_id,
            action=saved.action,
            device_type=saved.device_type,
            device_name=saved.device_name,
            duration=saved.duration,
            amount=saved.amount,
        )

    async def confirm_payment(self, cmd: ConfirmPayment) -> ConfirmPaymentResult:
        pending = await self._pending_gateway.get_by_id(cmd.pending_id)
        if pending is None:
            raise PendingPaymentNotFound(cmd.pending_id)

        device_name: str
        end_date: datetime | None = None

        if pending.action == "new":
            device_name = await self._generate_device_name(pending.device_type)
            await self._save_device(
                CreateDevice(
                    telegram_id=pending.user_telegram_id,
                    device_type=pending.device_type,
                    period_months=pending.duration,
                    amount=pending.amount,
                    balance_to_deduct=pending.balance_to_deduct,
                    vpn_config=None,
                ),
                device_name=device_name,
            )
        elif pending.action == "renew":
            if pending.device_name is None:
                raise DeviceNotFound(device_name="(None)")
            renew_info = await self._save_renewal(
                RenewSubscription(
                    device_name=pending.device_name,
                    period_months=pending.duration,
                    amount=pending.amount,
                    balance_to_deduct=pending.balance_to_deduct,
                )
            )
            device_name = renew_info.device_name
            end_date = renew_info.end_date
        else:
            raise ValueError(f"Unknown pending action: {pending.action}")

        await self._pending_gateway.delete(cmd.pending_id)
        await self._uow.commit()

        return ConfirmPaymentResult(
            user_telegram_id=pending.user_telegram_id,
            device_name=device_name,
            action=pending.action,
            vless_link=None,
            end_date=end_date,
        )

    async def _save_device(
        self, cmd: CreateDevice, device_name: str
    ) -> None:
        user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserDeviceNotFound(cmd.telegram_id)

        now = datetime.now(UTC)
        end_date = now + relativedelta(months=cmd.period_months)
        subscription = Subscription(device_id=0, plan=cmd.period_months, start_date=now, end_date=end_date)
        subscription.payments = [Payment(subscription_id=0, amount=cmd.amount, payment_date=now)]  # type: ignore[attr-defined]
        device = Device(
            user_id=user.telegram_id,
            device_name=device_name,
            created_at=now,
            vpn_config=cmd.vpn_config,
            vpn_client_uuid=None,
            subscription=subscription,
        )

        if cmd.balance_to_deduct > 0:
            if user.balance < cmd.balance_to_deduct:
                raise InsufficientBalance(cmd.telegram_id, user.balance, cmd.balance_to_deduct)
            user.balance -= cmd.balance_to_deduct
            await self._user_gateway.save(user)

        await self._gateway.save(device)

    async def _save_renewal(self, cmd: RenewSubscription) -> SubscriptionInfo:
        device = await self._gateway.get_by_name(cmd.device_name)
        if device is None:
            raise DeviceNotFound(device_name=cmd.device_name)
        if device.subscription is None:
            raise SubscriptionNotFound(device.id or 0)

        now = datetime.now(UTC)
        sub = device.subscription
        base = sub.end_date if sub.end_date > now else now
        sub.end_date = base + relativedelta(months=cmd.period_months)
        sub.plan = cmd.period_months
        sub.start_date = now

        if cmd.balance_to_deduct > 0:
            renewal_user = await self._user_gateway.get_by_telegram_id(device.user_id)
            if renewal_user is None:
                raise UserDeviceNotFound(device.user_id)
            if renewal_user.balance < cmd.balance_to_deduct:
                raise InsufficientBalance(device.user_id, renewal_user.balance, cmd.balance_to_deduct)
            renewal_user.balance -= cmd.balance_to_deduct
            await self._user_gateway.save(renewal_user)

        await self._gateway.save(device)
        return SubscriptionInfo(device_name=device.device_name, end_date=sub.end_date, plan=sub.plan)

    async def reject_payment(self, cmd: RejectPayment) -> PendingPaymentInfo:
        pending = await self._pending_gateway.get_by_id(cmd.pending_id)
        if pending is None:
            raise PendingPaymentNotFound(cmd.pending_id)
        info = PendingPaymentInfo(
            id=pending.id,  # type: ignore[arg-type]
            user_telegram_id=pending.user_telegram_id,
            action=pending.action,
            device_type=pending.device_type,
            device_name=pending.device_name,
            duration=pending.duration,
            amount=pending.amount,
        )
        await self._pending_gateway.delete(cmd.pending_id)
        await self._uow.commit()
        return info

    async def _generate_device_name(self, device_type: str) -> str:
        seq = await self._gateway.get_next_seq()
        suffix = f"{seq}{random.randint(1, 5000)}"
        return f"{device_type} {suffix}"
```

- [ ] **Step 2: Запустить тесты interactor — ожидаем что некоторые упадут**

```bash
uv run pytest tests/unit/device/test_device_interactor.py -v
```

Ожидаемый вывод: тест `test_confirm_payment_new_creates_device_and_returns_vless` упадёт — в conftest ещё есть `xui_client`.

---

## Task 8: Обновить тесты — убрать mock_xui_client

**Files:**
- Modify: `tests/unit/device/conftest.py`
- Modify: `tests/unit/device/test_device_interactor.py`

- [ ] **Step 1: Обновить conftest.py**

Заменить полное содержимое `tests/unit/device/conftest.py`:

```python
import pytest
from unittest.mock import AsyncMock

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interactor import DeviceInteractor
from src.apps.user.application.interfaces.gateway import UserGateway
from src.infrastructure.database.uow import SQLAlchemyUoW


@pytest.fixture
def mock_gateway() -> AsyncMock:
    return AsyncMock(spec=DeviceGateway)


@pytest.fixture
def mock_user_gateway() -> AsyncMock:
    return AsyncMock(spec=UserGateway)


@pytest.fixture
def mock_uow() -> AsyncMock:
    return AsyncMock(spec=SQLAlchemyUoW)


@pytest.fixture
def mock_pending_gateway() -> AsyncMock:
    return AsyncMock(spec=PendingPaymentGateway)


@pytest.fixture
def interactor(
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_uow: AsyncMock,
    mock_pending_gateway: AsyncMock,
) -> DeviceInteractor:
    return DeviceInteractor(
        gateway=mock_gateway,
        user_gateway=mock_user_gateway,
        uow=mock_uow,
        pending_gateway=mock_pending_gateway,
    )
```

- [ ] **Step 2: Обновить test_confirm_payment_new в test_device_interactor.py**

Найти тест `test_confirm_payment_new_creates_device_and_returns_vless` (строки ~303–340) и заменить его:

```python
@pytest.mark.asyncio
async def test_confirm_payment_new_creates_device_and_returns_result(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    from datetime import UTC, datetime
    from src.apps.device.domain.models import PendingPayment
    from src.apps.device.domain.commands import ConfirmPayment
    from src.apps.user.domain.models import User

    pending = PendingPayment(
        id=5,
        user_telegram_id=123,
        action="new",
        device_type="Android",
        duration=1,
        amount=150,
        balance_to_deduct=0,
        created_at=datetime.now(UTC),
    )
    mock_pending_gateway.get_by_id.return_value = pending
    mock_gateway.get_next_seq.return_value = 1
    mock_user_gateway.get_by_telegram_id.return_value = User(telegram_id=123, balance=0)
    interactor._pending_gateway = mock_pending_gateway

    result = await interactor.confirm_payment(ConfirmPayment(pending_id=5))

    assert result.action == "new"
    assert result.vless_link is None  # временно None — Remnawave flow в следующем этапе
    assert result.user_telegram_id == 123
    mock_pending_gateway.delete.assert_called_once_with(5)
    mock_gateway.save.assert_called_once()
```

- [ ] **Step 3: Запустить все тесты device — все должны пройти**

```bash
uv run pytest tests/unit/device/ -v
```

Ожидаемый вывод: все тесты `PASSED` (test_xui_client.py ещё есть, но пройдёт).

- [ ] **Step 4: Commit**

```bash
git add src/apps/device/application/interactor.py tests/unit/device/conftest.py tests/unit/device/test_device_interactor.py
git commit -m "refactor: remove XuiClient from DeviceInteractor, simplify confirm_payment"
```

---

## Task 9: Обновить IoC — зарегистрировать RemnawaveClient

**Files:**
- Modify: `src/apps/device/ioc.py`

- [ ] **Step 1: Заменить ioc.py**

Заменить полное содержимое `src/apps/device/ioc.py`:

```python
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.gateway import (
    SQLAlchemyDeviceGateway,
    SQLAlchemyPendingPaymentGateway,
)
from src.apps.device.adapters.remnawave_gateway import RemnawaveGatewayImpl
from src.apps.device.adapters.view import SQLAlchemyDeviceView
from src.apps.device.application.interactor import DeviceInteractor
from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.user.application.interfaces.gateway import UserGateway
from src.infrastructure.config import AppConfig
from src.infrastructure.database.uow import SQLAlchemyUoW
from src.infrastructure.remnawave.client import RemnawaveClient


class DeviceProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_gateway(self, session: AsyncSession) -> DeviceGateway:
        return SQLAlchemyDeviceGateway(session)

    @provide
    def get_pending_gateway(self, session: AsyncSession) -> PendingPaymentGateway:
        return SQLAlchemyPendingPaymentGateway(session)

    @provide
    def get_view(self, session: AsyncSession) -> DeviceView:
        return SQLAlchemyDeviceView(session)

    @provide(scope=Scope.APP)
    def get_remnawave_client(self, config: AppConfig) -> RemnawaveClient:
        return RemnawaveClient(config.remnawave)

    @provide
    def get_remnawave_gateway(self, client: RemnawaveClient) -> RemnawaveGateway:
        return RemnawaveGatewayImpl(client)

    @provide
    def get_interactor(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        pending_gateway: PendingPaymentGateway,
    ) -> DeviceInteractor:
        return DeviceInteractor(
            gateway=gateway,
            user_gateway=user_gateway,
            uow=uow,
            pending_gateway=pending_gateway,
        )
```

- [ ] **Step 2: Проверить что модуль импортируется без ошибок**

```bash
uv run python -c "from src.apps.device.ioc import DeviceProvider; print('OK')"
```

Ожидаемый вывод: `OK`.

- [ ] **Step 3: Commit**

```bash
git add src/apps/device/ioc.py
git commit -m "refactor: replace XuiClient with RemnawaveClient in DeviceProvider IoC"
```

---

## Task 10: Удалить XuiClient

**Files:**
- Delete: `src/infrastructure/xui/` (весь каталог)
- Delete: `tests/unit/device/test_xui_client.py`

- [ ] **Step 1: Удалить xui-каталог и тест**

```bash
rm -rf src/infrastructure/xui/
rm tests/unit/device/test_xui_client.py
```

- [ ] **Step 2: Запустить весь тестовый набор**

```bash
uv run pytest tests/unit/ -v
```

Ожидаемый вывод: все тесты `PASSED`, нет импортных ошибок.

- [ ] **Step 3: Проверить что нет оставшихся ссылок на xui**

```bash
grep -r "xui\|XuiClient\|XuiSettings" src/ tests/ --include="*.py"
```

Ожидаемый вывод: пустой (нет совпадений).

- [ ] **Step 4: Финальный commit**

```bash
git add -A
git commit -m "feat: complete Remnawave API client layer, remove XuiClient"
```

---

## Итоговая проверка

После выполнения всех задач:

```bash
uv run pytest tests/unit/ -v
```

Ожидаемый вывод: все тесты проходят, включая:
- `tests/unit/infrastructure/test_remnawave_client.py` — 11 тестов
- `tests/unit/device/test_remnawave_gateway.py` — 8 тестов
- `tests/unit/device/test_device_interactor.py` — 11 тестов
- `tests/unit/user/test_user_interactor.py` — без изменений

Граф зависимостей после выполнения:
```
DeviceInteractor ← RemnawaveGateway (Protocol)
                         ↑
                  RemnawaveGatewayImpl
                         ↑
                   RemnawaveClient
                         ↑
                  RemnawaveSettings (REMNAWAVE__URL, REMNAWAVE__TOKEN)
```
