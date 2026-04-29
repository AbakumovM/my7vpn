# Admin Confirm + 3x-ui Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить немедленное создание VPN-устройства при нажатии "Я оплатил" на двухшаговый флоу — ожидание подтверждения от админа, после которого система автоматически создаёт клиента в 3x-ui и отправляет VLESS-ссылку пользователю.

**Architecture:** Вводим `PendingPayment` — запись в БД о платеже в ожидании подтверждения. Админ получает уведомление с кнопками [✅ Подтвердить / ❌ Отклонить]. При подтверждении `DeviceInteractor.confirm_payment()` создаёт устройство в БД, вызывает `XuiClient.add_client()` для 3x-ui и возвращает VLESS-ссылку боту для доставки пользователю.

**Tech Stack:** Python 3.12, Aiogram 3.18, SQLAlchemy 2 async, Dishka, httpx, Alembic, structlog

---

## Карта файлов

| Действие | Файл | Что делает |
|----------|------|-----------|
| Create | `src/infrastructure/xui/__init__.py` | пакет |
| Create | `src/infrastructure/xui/client.py` | XuiClient — HTTP к 3x-ui |
| Modify | `src/infrastructure/config.py` | + XuiSettings, + xui поле в AppConfig |
| Modify | `src/apps/device/domain/models.py` | + PendingPayment dataclass |
| Modify | `src/apps/device/domain/exceptions.py` | + PendingPaymentNotFound |
| Modify | `src/apps/device/domain/commands.py` | + CreatePendingPayment, ConfirmPayment, RejectPayment; + vpn_config в CreateDevice |
| Modify | `src/apps/device/adapters/orm.py` | + PendingPaymentORM |
| Create | `alembic/versions/xxxx_add_pending_payments.py` | миграция |
| Create | `src/apps/device/application/interfaces/pending_gateway.py` | PendingPaymentGateway Protocol |
| Modify | `src/apps/device/adapters/gateway.py` | + SQLAlchemyPendingPaymentGateway |
| Modify | `src/apps/device/application/interactor.py` | + create_pending_payment, confirm_payment, reject_payment; + vpn_config в create_device |
| Modify | `src/common/bot/cbdata.py` | + AdminConfirmCallback |
| Modify | `src/common/bot/keyboards/keyboards.py` | + get_keyboard_admin_confirm, + get_keyboard_vpn_received |
| Modify | `src/apps/device/controllers/bot/router.py` | изменить 6a/6b, добавить admin confirm/reject |
| Modify | `src/apps/device/ioc.py` | зарегистрировать PendingPaymentGateway, XuiClient |
| Modify | `pyproject.toml` | + httpx |
| Modify | `alembic/env.py` | импорт PendingPaymentORM уже через device orm |
| Create | `tests/unit/device/test_xui_client.py` | тесты XuiClient |

---

## Task 1: httpx + XuiSettings в конфиге

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/infrastructure/config.py`

- [ ] **Step 1: Добавить httpx в зависимости**

В `pyproject.toml` в секцию `dependencies` добавить строку после `aiosmtplib`:
```toml
"httpx>=0.27.0",
```

- [ ] **Step 2: Установить зависимости**

```bash
cd /Users/mihailabakumov/Desktop/vpn && uv sync
```
Ожидание: `Resolved ... packages`

- [ ] **Step 3: Добавить XuiSettings в config.py**

Читать `/Users/mihailabakumov/Desktop/vpn/src/infrastructure/config.py`.

После класса `SmtpSettings` добавить:
```python
class XuiSettings(BaseModel):
    url: str = ""                   # http://62.133.60.207:57385/vps7my
    username: str = ""              # логин панели 3x-ui
    password: str = ""              # пароль панели 3x-ui
    inbound_id: int = 1             # ID инбаунда VLESS в 3x-ui
    vless_template: str = ""        # vless://{uuid}@host:port?params#{name}
```

В класс `AppConfig` добавить поле (после `smtp`):
```python
xui: XuiSettings = Field(default_factory=XuiSettings)
```

- [ ] **Step 4: Проверить импорт**

```bash
uv run python -c "from src.infrastructure.config import app_config; print(app_config.xui)"
```
Ожидание: `url='' username='' ...`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/infrastructure/config.py uv.lock
git commit -m "feat: add XuiSettings to config and httpx dependency"
```

---

## Task 2: XuiClient

**Files:**
- Create: `src/infrastructure/xui/__init__.py`
- Create: `src/infrastructure/xui/client.py`
- Create: `tests/unit/device/test_xui_client.py`

- [ ] **Step 1: Написать падающий тест**

Создать `tests/unit/device/test_xui_client.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.infrastructure.xui.client import XuiClient
from src.infrastructure.config import XuiSettings


def make_client() -> XuiClient:
    settings = XuiSettings(
        url="http://localhost:57385/panel",
        username="admin",
        password="secret",
        inbound_id=1,
        vless_template="vless://{uuid}@host:443?params#{name}",
    )
    return XuiClient(settings)


@pytest.mark.asyncio
async def test_add_client_returns_vless_link() -> None:
    """add_client логинится, добавляет клиента, возвращает VLESS-ссылку."""
    client = make_client()

    mock_response_login = MagicMock()
    mock_response_login.raise_for_status = MagicMock()

    mock_response_add = MagicMock()
    mock_response_add.raise_for_status = MagicMock()
    mock_response_add.json.return_value = {"success": True}

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(side_effect=[mock_response_login, mock_response_add])
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)

    with patch("src.infrastructure.xui.client.httpx.AsyncClient", return_value=mock_http):
        link = await client.add_client("Android 11234")

    assert link.startswith("vless://")
    assert "Android 11234" in link
    assert mock_http.post.call_count == 2
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
cd /Users/mihailabakumov/Desktop/vpn && uv run pytest tests/unit/device/test_xui_client.py -v
```
Ожидание: `FAILED` — `ModuleNotFoundError: src.infrastructure.xui.client`

- [ ] **Step 3: Создать пакет**

Создать пустой файл `src/infrastructure/xui/__init__.py`.

- [ ] **Step 4: Создать XuiClient**

Создать `src/infrastructure/xui/client.py`:

```python
import uuid as uuid_lib

import httpx
import structlog

from src.infrastructure.config import XuiSettings

log = structlog.get_logger(__name__)


class XuiClient:
    def __init__(self, settings: XuiSettings) -> None:
        self._settings = settings

    async def add_client(self, client_name: str) -> str:
        """
        Логинится в 3x-ui, добавляет VLESS-клиента, возвращает ссылку подключения.

        Шаги:
        1. POST {url}/login — получить сессионную куку
        2. POST {url}/panel/api/inbounds/addClient — добавить клиента
        3. Подставить uuid + name в vless_template

        Raises:
            httpx.HTTPStatusError: если 3x-ui вернул ошибку HTTP
            RuntimeError: если 3x-ui вернул success=False
        """
        client_uuid = str(uuid_lib.uuid4())
        s = self._settings

        async with httpx.AsyncClient(base_url=s.url, timeout=15.0) as http:
            # 1. Логин
            login_resp = await http.post(
                "/login",
                data={"username": s.username, "password": s.password},
            )
            login_resp.raise_for_status()
            log.debug("xui_login_ok")

            # 2. Добавить клиента
            payload = {
                "id": s.inbound_id,
                "settings": (
                    '{"clients": [{"id": "'
                    + client_uuid
                    + '", "email": "'
                    + client_name
                    + '", "enable": true, "expiryTime": 0}]}'
                ),
            }
            add_resp = await http.post("/panel/api/inbounds/addClient", json=payload)
            add_resp.raise_for_status()
            result = add_resp.json()
            if not result.get("success"):
                raise RuntimeError(f"3x-ui addClient failed: {result}")

        log.info("xui_client_added", client_name=client_name, uuid=client_uuid)

        # 3. Сформировать VLESS-ссылку из шаблона
        return s.vless_template.format(uuid=client_uuid, name=client_name)
```

- [ ] **Step 5: Запустить тест — должен пройти**

```bash
uv run pytest tests/unit/device/test_xui_client.py -v
```
Ожидание: `PASSED`

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/xui/__init__.py src/infrastructure/xui/client.py tests/unit/device/test_xui_client.py
git commit -m "feat: add XuiClient for automated 3x-ui VLESS client creation"
```

---

## Task 3: PendingPayment — домен

**Files:**
- Modify: `src/apps/device/domain/models.py`
- Modify: `src/apps/device/domain/exceptions.py`
- Modify: `src/apps/device/domain/commands.py`

- [ ] **Step 1: Добавить PendingPayment в models.py**

Читать `src/apps/device/domain/models.py`. Добавить в конец файла:

```python
@dataclass
class PendingPayment:
    user_telegram_id: int
    action: str                   # "new" | "renew"
    device_type: str              # "Android", "iOS", "TV", "Windows", "MacOS"
    duration: int                 # месяцев
    amount: int                   # к оплате
    balance_to_deduct: int
    created_at: datetime
    device_name: str | None = None  # None для new, имя устройства для renew
    id: int | None = None
```

- [ ] **Step 2: Добавить PendingPaymentNotFound в exceptions.py**

Читать `src/apps/device/domain/exceptions.py`. Добавить в конец:

```python
class PendingPaymentNotFound(Exception):
    def __init__(self, pending_id: int) -> None:
        super().__init__(f"PendingPayment id={pending_id} not found")
        self.pending_id = pending_id
```

- [ ] **Step 3: Добавить команды в commands.py**

Читать `src/apps/device/domain/commands.py`.

Добавить поле `vpn_config` в `CreateDevice`:
```python
@dataclass(frozen=True)
class CreateDevice:
    telegram_id: int
    device_type: str
    period_months: int
    amount: int
    balance_to_deduct: int = 0
    vpn_config: str | None = None   # ← добавить
```

Добавить новые команды в конец файла:
```python
@dataclass(frozen=True)
class CreatePendingPayment:
    user_telegram_id: int
    action: str            # "new" | "renew"
    device_type: str
    duration: int
    amount: int
    balance_to_deduct: int
    device_name: str | None = None  # None для new, имя для renew


@dataclass(frozen=True)
class ConfirmPayment:
    pending_id: int


@dataclass(frozen=True)
class RejectPayment:
    pending_id: int
```

- [ ] **Step 4: Проверить импорты**

```bash
uv run python -c "
from src.apps.device.domain.models import PendingPayment
from src.apps.device.domain.exceptions import PendingPaymentNotFound
from src.apps.device.domain.commands import CreatePendingPayment, ConfirmPayment, RejectPayment
print('OK')
"
```
Ожидание: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/apps/device/domain/models.py src/apps/device/domain/exceptions.py src/apps/device/domain/commands.py
git commit -m "feat: add PendingPayment domain model, exceptions, and commands"
```

---

## Task 4: PendingPaymentORM + Alembic миграция

**Files:**
- Modify: `src/apps/device/adapters/orm.py`
- Create: `alembic/versions/xxxx_add_pending_payments_table.py` (генерируется)

- [ ] **Step 1: Добавить PendingPaymentORM в orm.py**

Читать `src/apps/device/adapters/orm.py`. Добавить в конец файла:

```python
from sqlalchemy import BigInteger  # добавить в существующий import


class PendingPaymentORM(Base):
    __tablename__ = "pending_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_telegram_id = Column(BigInteger, nullable=False)
    action = Column(String(10), nullable=False)       # "new" | "renew"
    device_type = Column(String(20), nullable=False)
    device_name = Column(String(100), nullable=True)  # для renew
    duration = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)
    balance_to_deduct = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)
```

Примечание: `BigInteger` добавить к существующему импорту из `sqlalchemy`:
```python
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String
```

- [ ] **Step 2: Проверить импорт ORM**

```bash
uv run python -c "from src.apps.device.adapters.orm import PendingPaymentORM; print('OK')"
```
Ожидание: `OK`

- [ ] **Step 3: Сгенерировать миграцию**

```bash
uv run alembic revision --autogenerate -m "add pending_payments table"
```
Ожидание: `Generating .../alembic/versions/xxxx_add_pending_payments_table.py`

- [ ] **Step 4: Проверить сгенерированный файл миграции**

Открыть сгенерированный файл и убедиться что в `upgrade()` есть `op.create_table('pending_payments', ...)` с нужными колонками. Если файл пустой или неверный — проверить что `PendingPaymentORM` импортируется в `alembic/env.py` через `import src.apps.device.adapters.orm`.

- [ ] **Step 5: Commit**

```bash
git add src/apps/device/adapters/orm.py alembic/versions/
git commit -m "feat: add PendingPaymentORM and migration for pending_payments table"
```

---

## Task 5: PendingPaymentGateway — Protocol и SQLAlchemy адаптер

**Files:**
- Create: `src/apps/device/application/interfaces/pending_gateway.py`
- Modify: `src/apps/device/adapters/gateway.py`

- [ ] **Step 1: Создать Protocol**

Создать `src/apps/device/application/interfaces/pending_gateway.py`:

```python
from typing import Protocol

from src.apps.device.domain.models import PendingPayment


class PendingPaymentGateway(Protocol):
    async def save(self, pending: PendingPayment) -> PendingPayment: ...
    async def get_by_id(self, pending_id: int) -> PendingPayment | None: ...
    async def delete(self, pending_id: int) -> None: ...
```

- [ ] **Step 2: Написать падающий тест**

Добавить в `tests/unit/device/conftest.py` фикстуру для mock pending gateway.

Читать `tests/unit/device/conftest.py`. Добавить:

```python
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway

@pytest.fixture
def mock_pending_gateway() -> AsyncMock:
    return AsyncMock(spec=PendingPaymentGateway)
```

Добавить в `tests/unit/device/test_device_interactor.py`:

```python
@pytest.mark.asyncio
async def test_create_pending_payment_saves_and_returns(
    interactor: DeviceInteractor,
    mock_pending_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    from datetime import UTC, datetime
    from src.apps.device.domain.models import PendingPayment
    from src.apps.device.domain.commands import CreatePendingPayment

    saved_pending = PendingPayment(
        id=1,
        user_telegram_id=123,
        action="new",
        device_type="Android",
        duration=1,
        amount=150,
        balance_to_deduct=0,
        created_at=datetime.now(UTC),
    )
    mock_pending_gateway.save.return_value = saved_pending
    interactor._pending_gateway = mock_pending_gateway

    cmd = CreatePendingPayment(
        user_telegram_id=123,
        action="new",
        device_type="Android",
        duration=1,
        amount=150,
        balance_to_deduct=0,
    )
    result = await interactor.create_pending_payment(cmd)

    mock_pending_gateway.save.assert_called_once()
    mock_uow.commit.assert_called_once()
    assert result.id == 1
    assert result.user_telegram_id == 123
```

- [ ] **Step 3: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/unit/device/test_device_interactor.py::test_create_pending_payment_saves_and_returns -v
```
Ожидание: `FAILED` — `AttributeError: 'DeviceInteractor' object has no attribute '_pending_gateway'`

- [ ] **Step 4: Создать SQLAlchemyPendingPaymentGateway**

В `src/apps/device/adapters/gateway.py` добавить в конец файла:

```python
from src.apps.device.adapters.orm import PendingPaymentORM  # добавить к существующим импортам
from src.apps.device.domain.models import PendingPayment    # добавить к существующим импортам
from sqlalchemy import select                               # уже есть


class SQLAlchemyPendingPaymentGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, pending: PendingPayment) -> PendingPayment:
        if pending.id is None:
            orm = PendingPaymentORM(
                user_telegram_id=pending.user_telegram_id,
                action=pending.action,
                device_type=pending.device_type,
                device_name=pending.device_name,
                duration=pending.duration,
                amount=pending.amount,
                balance_to_deduct=pending.balance_to_deduct,
                created_at=pending.created_at,
            )
            self._session.add(orm)
            await self._session.flush()
            pending.id = orm.id  # type: ignore[misc]
        return pending

    async def get_by_id(self, pending_id: int) -> PendingPayment | None:
        result = await self._session.execute(
            select(PendingPaymentORM).where(PendingPaymentORM.id == pending_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return PendingPayment(
            id=row.id,
            user_telegram_id=row.user_telegram_id,
            action=row.action,
            device_type=row.device_type,
            device_name=row.device_name,
            duration=row.duration,
            amount=row.amount,
            balance_to_deduct=row.balance_to_deduct,
            created_at=row.created_at,
        )

    async def delete(self, pending_id: int) -> None:
        result = await self._session.execute(
            select(PendingPaymentORM).where(PendingPaymentORM.id == pending_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()
```

- [ ] **Step 5: Проверить импорт**

```bash
uv run python -c "from src.apps.device.adapters.gateway import SQLAlchemyPendingPaymentGateway; print('OK')"
```
Ожидание: `OK`

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/application/interfaces/pending_gateway.py src/apps/device/adapters/gateway.py tests/unit/device/conftest.py
git commit -m "feat: add PendingPaymentGateway protocol and SQLAlchemy adapter"
```

---

## Task 6: DeviceInteractor — новые методы

**Files:**
- Modify: `src/apps/device/application/interactor.py`
- Modify: `tests/unit/device/test_device_interactor.py`

- [ ] **Step 1: Обновить конструктор и добавить result-типы**

Читать `src/apps/device/application/interactor.py`.

В начало файла добавить импорты:
```python
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.domain.exceptions import PendingPaymentNotFound
from src.apps.device.domain.models import PendingPayment
from src.apps.device.domain.commands import ConfirmPayment, CreatePendingPayment, RejectPayment
from src.infrastructure.xui.client import XuiClient
```

Добавить новые frozen dataclass результаты после `SubscriptionInfo`:
```python
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
    vless_link: str | None   # None для renew
    end_date: datetime | None
```

Обновить конструктор `DeviceInteractor`:
```python
class DeviceInteractor:
    def __init__(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        pending_gateway: PendingPaymentGateway,
        xui_client: XuiClient,
    ) -> None:
        self._gateway = gateway
        self._user_gateway = user_gateway
        self._uow = uow
        self._pending_gateway = pending_gateway
        self._xui_client = xui_client
```

- [ ] **Step 2: Обновить create_device — добавить vpn_config**

В методе `create_device`, найти строку где создаётся `Device(...)` и добавить `vpn_config=cmd.vpn_config`:
```python
device = Device(
    user_id=user.telegram_id,
    device_name=device_name,
    created_at=now,
    vpn_config=cmd.vpn_config,   # ← добавить
    subscription=subscription_with_payment,
)
```

- [ ] **Step 3: Добавить create_pending_payment**

```python
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
```

- [ ] **Step 4: Добавить confirm_payment**

```python
async def confirm_payment(self, cmd: ConfirmPayment) -> ConfirmPaymentResult:
    pending = await self._pending_gateway.get_by_id(cmd.pending_id)
    if pending is None:
        raise PendingPaymentNotFound(cmd.pending_id)

    vless_link: str | None = None
    device_name: str
    end_date: datetime | None = None

    if pending.action == "new":
        device_name = await self._generate_device_name(pending.device_type)
        vless_link = await self._xui_client.add_client(device_name)
        result = await self.create_device(
            CreateDevice(
                telegram_id=pending.user_telegram_id,
                device_type=pending.device_type,
                period_months=pending.duration,
                amount=pending.amount,
                balance_to_deduct=pending.balance_to_deduct,
                vpn_config=vless_link,
            )
        )
        # create_device уже закоммитил. Теперь удаляем pending и коммитим ещё раз.
        device_name = result.device_name
    elif pending.action == "renew":
        if pending.device_name is None:
            raise DeviceNotFound(device_name="(None)")
        result_renew = await self.renew_subscription(
            RenewSubscription(
                device_name=pending.device_name,
                period_months=pending.duration,
                amount=pending.amount,
                balance_to_deduct=pending.balance_to_deduct,
            )
        )
        device_name = result_renew.device_name
        end_date = result_renew.end_date
    else:
        raise ValueError(f"Unknown pending action: {pending.action}")

    await self._pending_gateway.delete(cmd.pending_id)
    await self._uow.commit()

    return ConfirmPaymentResult(
        user_telegram_id=pending.user_telegram_id,
        device_name=device_name,
        action=pending.action,
        vless_link=vless_link,
        end_date=end_date,
    )
```

Добавить недостающие импорты (уже должны быть в файле, проверить):
- `CreateDevice` из `commands`
- `RenewSubscription` из `commands`
- `DeviceNotFound` из `exceptions`

- [ ] **Step 5: Добавить reject_payment**

```python
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
```

- [ ] **Step 6: Добавить тест create_pending_payment (уже написан в Task 5) — запустить**

```bash
uv run pytest tests/unit/device/test_device_interactor.py::test_create_pending_payment_saves_and_returns -v
```
Ожидание: `PASSED`

- [ ] **Step 7: Добавить тест confirm_payment для action=new**

В `tests/unit/device/test_device_interactor.py` добавить:

```python
@pytest.mark.asyncio
async def test_confirm_payment_new_creates_device_and_returns_vless(
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

    mock_xui = AsyncMock()
    mock_xui.add_client.return_value = "vless://uuid@host:443?params#Android_11"
    interactor._xui_client = mock_xui
    interactor._pending_gateway = mock_pending_gateway

    result = await interactor.confirm_payment(ConfirmPayment(pending_id=5))

    assert result.action == "new"
    assert result.vless_link == "vless://uuid@host:443?params#Android_11"
    assert result.user_telegram_id == 123
    mock_pending_gateway.delete.assert_called_once_with(5)
    mock_xui.add_client.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_payment_raises_if_not_found(
    interactor: DeviceInteractor,
    mock_pending_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    from src.apps.device.domain.commands import ConfirmPayment
    from src.apps.device.domain.exceptions import PendingPaymentNotFound

    mock_pending_gateway.get_by_id.return_value = None
    interactor._pending_gateway = mock_pending_gateway

    with pytest.raises(PendingPaymentNotFound):
        await interactor.confirm_payment(ConfirmPayment(pending_id=999))
```

- [ ] **Step 8: Запустить все device тесты**

```bash
uv run pytest tests/unit/device/ -v
```
Ожидание: все `PASSED` (включая новые)

- [ ] **Step 9: Commit**

```bash
git add src/apps/device/application/interactor.py tests/unit/device/test_device_interactor.py
git commit -m "feat: add create_pending_payment, confirm_payment, reject_payment to DeviceInteractor"
```

---

## Task 7: AdminConfirmCallback + клавиатуры

**Files:**
- Modify: `src/common/bot/cbdata.py`
- Modify: `src/common/bot/keyboards/keyboards.py`

- [ ] **Step 1: Добавить AdminConfirmCallback в cbdata.py**

Читать `src/common/bot/cbdata.py`. Добавить в конец:

```python
class AdminConfirmCallback(CallbackData, prefix="adm"):
    pending_id: int
    action: str   # "confirm" | "reject"
```

- [ ] **Step 2: Добавить get_keyboard_admin_confirm в keyboards.py**

Читать `src/common/bot/keyboards/keyboards.py`. Добавить импорт `AdminConfirmCallback`:
```python
from src.common.bot.cbdata import (
    AdminConfirmCallback,
    DeviceConfCallback,
    DeviceDeleteCallback,
    DeviceErrorCallback,
    SettingsCallback,
    VpnCallback,
)
```

Добавить функцию в конец файла:
```python
def get_keyboard_admin_confirm(pending_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=AdminConfirmCallback(
                    pending_id=pending_id, action="confirm"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=AdminConfirmCallback(
                    pending_id=pending_id, action="reject"
                ).pack(),
            ),
        ]
    ])
    return keyboard


def get_keyboard_vpn_received() -> InlineKeyboardMarkup:
    """Клавиатура после получения VPN-ключа: инструкция + главное меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📋 Инструкция по подключению",
                callback_data=CallbackAction.SUPPORT_HELP,
            )
        ],
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.START],
                callback_data=CallbackAction.START,
            )
        ],
    ])
    return keyboard
```

- [ ] **Step 3: Проверить импорты**

```bash
uv run python -c "
from src.common.bot.cbdata import AdminConfirmCallback
from src.common.bot.keyboards.keyboards import get_keyboard_admin_confirm, get_keyboard_vpn_received
kb = get_keyboard_admin_confirm(42)
print('OK', len(kb.inline_keyboard[0]), 'buttons')
"
```
Ожидание: `OK 2 buttons`

- [ ] **Step 4: Commit**

```bash
git add src/common/bot/cbdata.py src/common/bot/keyboards/keyboards.py
git commit -m "feat: add AdminConfirmCallback and admin/vpn keyboards"
```

---

## Task 8: Bot handler — изменить флоу оплаты и добавить admin handlers

**Files:**
- Modify: `src/apps/device/controllers/bot/router.py`

- [ ] **Step 1: Добавить импорты в router.py**

Читать `src/apps/device/controllers/bot/router.py`.

Добавить к импортам из `cbdata`:
```python
from src.common.bot.cbdata import AdminConfirmCallback, DeviceConfCallback, DeviceDeleteCallback, VpnCallback
```

Добавить к импортам из `keyboards`:
```python
from src.common.bot.keyboards.keyboards import (
    create_inline_kb,
    get_keyboard_admin_confirm,
    get_keyboard_approve_payment_or_cancel,
    get_keyboard_devices,
    get_keyboard_devices_for_del,
    get_keyboard_for_details_device,
    get_keyboard_skip_email,
    get_keyboard_start,
    get_keyboard_tariff,
    get_keyboard_type_device,
    get_keyboard_vpn_received,
    get_keyboard_yes_or_no_for_update,
    return_start,
)
```

Добавить к импортам из `device.domain.commands`:
```python
from src.apps.device.domain.commands import (
    ConfirmPayment,
    CreateDevice,
    CreateDeviceFree,
    CreatePendingPayment,
    DeleteDevice,
    RejectPayment,
    RenewSubscription,
)
```

Добавить к импортам из `device.domain.exceptions`:
```python
from src.apps.device.domain.exceptions import PendingPaymentNotFound
```

- [ ] **Step 2: Заменить шаг 6a (NEW_SUB + SUCCESS)**

Найти блок:
```python
# Шаг 6a: новая подписка — оплата успешна
if action == CallbackAction.NEW_SUB and payment_status == PaymentStatus.SUCCESS:
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        await call.answer()
        return
    await call.answer()
    result = await interactor.create_device(...)
    ...
    return
```

Заменить содержимое блока (сохранить try/except для идемпотентности):
```python
# Шаг 6a: новая подписка — оплата заявлена, ждём подтверждения админа
if action == CallbackAction.NEW_SUB and payment_status == PaymentStatus.SUCCESS:
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        await call.answer()
        return
    await call.answer()
    pending = await interactor.create_pending_payment(
        CreatePendingPayment(
            user_telegram_id=call.from_user.id,
            action="new",
            device_type=device,
            duration=duration,
            amount=payment,
            balance_to_deduct=balance,
        )
    )
    await call.message.delete()
    await call.message.answer("⏳ Ожидайте подтверждения оплаты администратором")
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"💳 Новый платёж!\n"
            f"👤 @{call.from_user.username} (id: {call.from_user.id})\n"
            f"📱 Устройство: {device}\n"
            f"📅 Срок: {duration} мес → {payment}₽"
        ),
        reply_markup=get_keyboard_admin_confirm(pending.id),
    )
    log.info(
        "pending_payment_created",
        pending_id=pending.id,
        user_id=call.from_user.id,
        device_type=device,
        duration=duration,
        amount=payment,
    )
    return
```

- [ ] **Step 3: Заменить шаг 6b (RENEW + SUCCESS)**

Найти блок:
```python
# Шаг 6b: продление подписки
if action == VpnAction.RENEW and payment_status == PaymentStatus.SUCCESS:
```

Заменить содержимое:
```python
# Шаг 6b: продление — ждём подтверждения админа
if action == VpnAction.RENEW and payment_status == PaymentStatus.SUCCESS:
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        await call.answer()
        return
    await call.answer()
    device_name_for_renew = callback_data.device_name or device
    pending = await interactor.create_pending_payment(
        CreatePendingPayment(
            user_telegram_id=call.from_user.id,
            action="renew",
            device_type=device,
            duration=duration,
            amount=payment,
            balance_to_deduct=balance,
            device_name=device_name_for_renew,
        )
    )
    await call.message.delete()
    await call.message.answer("⏳ Ожидайте подтверждения оплаты администратором")
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"🔄 Продление подписки!\n"
            f"👤 @{call.from_user.username} (id: {call.from_user.id})\n"
            f"📱 Устройство: {device_name_for_renew}\n"
            f"📅 Срок: {duration} мес → {payment}₽"
        ),
        reply_markup=get_keyboard_admin_confirm(pending.id),
    )
    log.info(
        "pending_renewal_created",
        pending_id=pending.id,
        user_id=call.from_user.id,
        device_name=device_name_for_renew,
        duration=duration,
        amount=payment,
    )
    return
```

- [ ] **Step 4: Добавить admin confirm handler**

В конец файла добавить два новых хендлера:

```python
@router.callback_query(AdminConfirmCallback.filter(F.action == "confirm"))
async def handle_admin_confirm(
    call: types.CallbackQuery,
    callback_data: AdminConfirmCallback,
    bot: Bot,
    interactor: FromDishka[DeviceInteractor],
) -> None:
    try:
        result = await interactor.confirm_payment(ConfirmPayment(pending_id=callback_data.pending_id))
    except PendingPaymentNotFound:
        await call.message.edit_text("⚠️ Платёж не найден — возможно, уже обработан")
        await call.answer()
        return
    except Exception:
        log.exception("admin_confirm_error", pending_id=callback_data.pending_id)
        await call.message.edit_text("❌ Ошибка при подтверждении. Проверьте логи.")
        await call.answer()
        return

    if result.action == "new" and result.vless_link:
        await bot.send_message(
            chat_id=result.user_telegram_id,
            text="✅ Оплата подтверждена! Ключ готов 👇",
        )
        await bot.send_message(
            chat_id=result.user_telegram_id,
            text=f"`{result.vless_link}`",
            parse_mode="Markdown",
            reply_markup=get_keyboard_vpn_received(),
        )
    else:
        end_str = result.end_date.strftime("%d.%m.%Y") if result.end_date else "—"
        await bot.send_message(
            chat_id=result.user_telegram_id,
            text=f"✅ Оплата подтверждена! Подписка продлена до {end_str}.",
            reply_markup=return_start(),
        )

    await call.message.edit_text(f"✅ Выдано: {result.device_name}")
    await call.answer("Готово!")
    log.info(
        "payment_confirmed",
        pending_id=callback_data.pending_id,
        device_name=result.device_name,
        action=result.action,
    )


@router.callback_query(AdminConfirmCallback.filter(F.action == "reject"))
async def handle_admin_reject(
    call: types.CallbackQuery,
    callback_data: AdminConfirmCallback,
    bot: Bot,
    interactor: FromDishka[DeviceInteractor],
) -> None:
    try:
        result = await interactor.reject_payment(RejectPayment(pending_id=callback_data.pending_id))
    except PendingPaymentNotFound:
        await call.message.edit_text("⚠️ Платёж не найден — возможно, уже обработан")
        await call.answer()
        return

    await bot.send_message(
        chat_id=result.user_telegram_id,
        text="❌ Оплата не подтверждена. Обратитесь к @my7vpnadmin",
    )
    await call.message.edit_text("Отклонено")
    await call.answer()
    log.info("payment_rejected", pending_id=callback_data.pending_id)
```

- [ ] **Step 5: Проверить что роутер импортируется**

```bash
uv run python -c "from src.apps.device.controllers.bot.router import router; print('OK')"
```
Ожидание: `OK`

- [ ] **Step 6: Запустить тесты**

```bash
uv run pytest tests/unit/ -v 2>&1 | tail -10
```
Ожидание: все device тесты `PASSED`

- [ ] **Step 7: Commit**

```bash
git add src/apps/device/controllers/bot/router.py
git commit -m "feat: replace immediate device creation with pending payment flow, add admin confirm/reject handlers"
```

---

## Task 9: DI — обновить DeviceProvider

**Files:**
- Modify: `src/apps/device/ioc.py`

- [ ] **Step 1: Обновить DeviceProvider**

Читать `src/apps/device/ioc.py`. Заменить весь файл на:

```python
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.gateway import (
    SQLAlchemyDeviceGateway,
    SQLAlchemyPendingPaymentGateway,
)
from src.apps.device.adapters.view import SQLAlchemyDeviceView
from src.apps.device.application.interactor import DeviceInteractor
from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.user.application.interfaces.gateway import UserGateway
from src.infrastructure.config import AppConfig
from src.infrastructure.database.uow import SQLAlchemyUoW
from src.infrastructure.xui.client import XuiClient


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
    def get_xui_client(self, config: AppConfig) -> XuiClient:
        return XuiClient(config.xui)

    @provide
    def get_interactor(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        pending_gateway: PendingPaymentGateway,
        xui_client: XuiClient,
    ) -> DeviceInteractor:
        return DeviceInteractor(
            gateway=gateway,
            user_gateway=user_gateway,
            uow=uow,
            pending_gateway=pending_gateway,
            xui_client=xui_client,
        )
```

- [ ] **Step 2: Проверить что контейнер собирается**

```bash
uv run python -c "
from src.infrastructure.config import app_config
from ioc import create_container
container = create_container(app_config)
print('OK')
"
```
Ожидание: `OK`

- [ ] **Step 3: Запустить все тесты**

```bash
uv run pytest tests/unit/ -v 2>&1 | tail -15
```
Ожидание: все `PASSED`

- [ ] **Step 4: Проверить ruff**

```bash
uv run ruff check --fix && uv run ruff format
```
Ожидание: нет ошибок

- [ ] **Step 5: Commit**

```bash
git add src/apps/device/ioc.py
git commit -m "feat: wire PendingPaymentGateway and XuiClient into DeviceProvider"
```

---

## Финальная проверка

- [ ] **Проверить запуск бота**

```bash
uv run python -c "import main_bot; print('bot import OK')"
```

- [ ] **Применить миграцию (на dev БД)**

```bash
uv run alembic upgrade head
```

- [ ] **Обновить .env — добавить XUI переменные**

В `.env` файл добавить:
```
XUI__URL=http://62.133.60.207:57385/vps7my
XUI__USERNAME=<admin_логин>
XUI__PASSWORD=<admin_пароль>
XUI__INBOUND_ID=<id_инбаунда>
XUI__VLESS_TEMPLATE=vless://{uuid}@62.133.60.207:443/?type=grpc&serviceName=&authority=&security=reality&pbk=veL6JjshQunKETu6Rr0WNfE6rUT7tOQncje7Qc2x8mc&fp=chrome&sni=kicker.de&sid=278e&spx=%2F#{name}
```

- [ ] **Открыть порт на VPN-сервере**

На сервере 62.133.60.207:
```bash
ufw allow from <IP_БОТ_СЕРВЕРА> to any port 57385
```
