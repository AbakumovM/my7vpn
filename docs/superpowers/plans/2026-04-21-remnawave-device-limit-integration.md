# Remnawave Device Limit & Subscription Flow Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Интегрировать Remnawave в flow создания/продления подписки с выбором лимита устройств (1/2/3): новые пользователи сразу получают Remnawave-аккаунт, существующие мигрируют при следующем продлении.

**Architecture:** `confirm_payment` вызывает `RemnawaveGateway.create_user` / `update_user` после сохранения устройства в сессию — до коммита, чтобы Remnawave-ошибка откатывала всю транзакцию. `remnawave_uuid` и `subscription_url` хранятся на `User`. `device_limit` передаётся через `PendingPayment` → `confirm_payment` → Remnawave и сохраняется на `Device`.

**Tech Stack:** Python 3.12, SQLAlchemy async, Aiogram 3, Dishka, httpx/respx, pytest-asyncio

---

## Файловая структура

**Изменить:**
- `src/apps/device/domain/models.py` — добавить `device_limit: int = 1` в `Device`, `PendingPayment`
- `src/apps/device/domain/commands.py` — добавить `device_limit: int = 1` в `CreateDevice`, `CreatePendingPayment`, `RenewSubscription`
- `src/apps/device/adapters/orm.py` — добавить колонки `device_limit` в `DeviceORM`, `PendingPaymentORM`
- `src/apps/device/adapters/gateway.py` — маппинг `device_limit` в `save` и `_to_domain` для обоих gateway
- `src/apps/device/application/interactor.py` — инжектировать `RemnawaveGateway`, Remnawave-вызовы в `confirm_payment`, `subscription_url` вместо `vless_link`
- `src/apps/device/ioc.py` — добавить `RemnawaveGateway` в конструктор `DeviceInteractor`
- `tests/unit/device/conftest.py` — добавить `mock_remnawave_gateway` и обновить `interactor` fixture
- `tests/unit/device/test_device_interactor.py` — обновить существующий тест + добавить тесты Remnawave-интеграции
- `src/common/bot/cbdata.py` — добавить `device_limit: int | None = None` в `VpnCallback`
- `src/common/bot/keyboards/user_actions.py` — добавить `TARIFF_MATRIX`
- `src/common/bot/keyboards/keyboards.py` — добавить `get_keyboard_device_count`, обновить `get_keyboard_tariff`
- `src/apps/device/controllers/bot/router.py` — шаг выбора кол-ва устройств, передача `device_limit` в `CreatePendingPayment`, обновление `handle_admin_confirm`

**Создать:**
- `alembic/versions/<id>_add_device_limit_to_devices_and_pending_payments.py`

---

## Task 1: Domain + commands — добавить device_limit

**Files:**
- Modify: `src/apps/device/domain/models.py`
- Modify: `src/apps/device/domain/commands.py`

- [ ] **Step 1: Обновить domain/models.py**

Полное содержимое `src/apps/device/domain/models.py`:

```python
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Subscription:
    device_id: int
    plan: int
    start_date: datetime
    end_date: datetime
    is_active: bool = True
    id: int | None = None


@dataclass
class Payment:
    subscription_id: int
    amount: int
    payment_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    currency: str = "RUB"
    payment_method: str = "карта"
    id: int | None = None


@dataclass
class Device:
    user_id: int
    device_name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    vpn_config: str | None = None
    vpn_client_uuid: str | None = None
    device_limit: int = 1
    id: int | None = None
    subscription: Subscription | None = None


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
    device_limit: int = 1
    id: int | None = None
```

- [ ] **Step 2: Обновить domain/commands.py**

Полное содержимое `src/apps/device/domain/commands.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CreateDevice:
    telegram_id: int
    device_type: str
    period_months: int
    amount: int
    balance_to_deduct: int = 0
    device_limit: int = 1
    vpn_config: str | None = None


@dataclass(frozen=True)
class CreateDeviceFree:
    telegram_id: int
    device_type: str
    period_days: int


@dataclass(frozen=True)
class DeleteDevice:
    device_id: int


@dataclass(frozen=True)
class RenewSubscription:
    device_name: str
    period_months: int
    amount: int
    balance_to_deduct: int = 0
    device_limit: int = 1


@dataclass(frozen=True)
class GetExpiringSubscriptions:
    pass


@dataclass(frozen=True)
class CreatePendingPayment:
    user_telegram_id: int
    action: str            # "new" | "renew"
    device_type: str
    duration: int
    amount: int
    balance_to_deduct: int
    device_limit: int = 1
    device_name: str | None = None  # None для new, имя для renew


@dataclass(frozen=True)
class ConfirmPayment:
    pending_id: int


@dataclass(frozen=True)
class RejectPayment:
    pending_id: int
```

- [ ] **Step 3: Проверить что модули импортируются без ошибок**

```bash
uv run python -c "from src.apps.device.domain.models import Device, PendingPayment; from src.apps.device.domain.commands import CreateDevice, CreatePendingPayment, RenewSubscription; print('OK')"
```

Ожидаемый вывод: `OK`.

- [ ] **Step 4: Commit**

```bash
git add src/apps/device/domain/models.py src/apps/device/domain/commands.py
git commit -m "feat: add device_limit to Device, PendingPayment domain models and commands"
```

---

## Task 2: ORM + gateway — persistence + migration

**Files:**
- Modify: `src/apps/device/adapters/orm.py`
- Modify: `src/apps/device/adapters/gateway.py`
- Create: `alembic/versions/<id>_add_device_limit_to_devices_and_pending_payments.py`

- [ ] **Step 1: Обновить orm.py — добавить device_limit в DeviceORM и PendingPaymentORM**

В `src/apps/device/adapters/orm.py` добавить `device_limit` в оба класса:

```python
from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.infrastructure.database.base import Base


class DeviceORM(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_name = Column(String, nullable=False)
    vpn_config = Column(String, nullable=True)
    vpn_client_uuid = Column(String(36), nullable=True)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    user = relationship("UserORM", back_populates="devices")
    subscription = relationship(
        "SubscriptionORM",
        uselist=False,
        back_populates="device",
        cascade="all, delete-orphan",
    )


class SubscriptionORM(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    plan = Column(Integer, nullable=False)
    start_date = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    is_active = Column(Boolean, default=True)
    end_date = Column(DateTime(timezone=True), nullable=False)

    device = relationship("DeviceORM", back_populates="subscription")
    payments = relationship(
        "PaymentORM", back_populates="subscription", cascade="all, delete-orphan"
    )


class PaymentORM(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(
        Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    amount = Column(Integer, nullable=False)
    currency = Column(String, default="RUB")
    payment_date = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    payment_method = Column(String, default="карта", nullable=True)

    subscription = relationship("SubscriptionORM", back_populates="payments")


class PendingPaymentORM(Base):
    __tablename__ = "pending_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_telegram_id = Column(BigInteger, nullable=False)
    action = Column(String(10), nullable=False)  # "new" | "renew"
    device_type = Column(String(20), nullable=False)
    device_name = Column(String(100), nullable=True)  # для renew
    duration = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)
    balance_to_deduct = Column(Integer, nullable=False, default=0)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 2: Обновить gateway.py — маппинг device_limit**

В `src/apps/device/adapters/gateway.py` обновить `SQLAlchemyDeviceGateway.save` (оба пути — создание и обновление) и `_to_domain`, а также оба метода `SQLAlchemyPendingPaymentGateway`:

В `save` (путь создания нового устройства — `if device.id is None`), строка создания `DeviceORM`:
```python
            device_orm = DeviceORM(
                user_id=user_orm.id,
                device_name=device.device_name,
                created_at=device.created_at,
                vpn_config=device.vpn_config,
                vpn_client_uuid=device.vpn_client_uuid,
                device_limit=device.device_limit,
            )
```

В `save` (путь обновления — `else`), после обновления подписки добавить:
```python
            device_orm.device_limit = device.device_limit
```

В `_to_domain`:
```python
    @staticmethod
    def _to_domain(row: DeviceORM) -> Device:
        sub: Subscription | None = None
        if row.subscription:
            s = row.subscription
            sub = Subscription(
                id=s.id,
                device_id=s.device_id,
                plan=s.plan,
                start_date=s.start_date,
                end_date=s.end_date,
                is_active=s.is_active,
            )
        return Device(
            id=row.id,
            user_id=row.user_id,
            device_name=row.device_name,
            vpn_config=row.vpn_config,
            vpn_client_uuid=row.vpn_client_uuid,
            device_limit=row.device_limit,
            created_at=row.created_at,
            subscription=sub,
        )
```

В `SQLAlchemyPendingPaymentGateway.save`:
```python
            orm = PendingPaymentORM(
                user_telegram_id=pending.user_telegram_id,
                action=pending.action,
                device_type=pending.device_type,
                device_name=pending.device_name,
                duration=pending.duration,
                amount=pending.amount,
                balance_to_deduct=pending.balance_to_deduct,
                device_limit=pending.device_limit,
                created_at=pending.created_at,
            )
```

В `SQLAlchemyPendingPaymentGateway.get_by_id` — в return:
```python
        return PendingPayment(
            id=row.id,
            user_telegram_id=row.user_telegram_id,
            action=row.action,
            device_type=row.device_type,
            device_name=row.device_name,
            duration=row.duration,
            amount=row.amount,
            balance_to_deduct=row.balance_to_deduct,
            device_limit=row.device_limit,
            created_at=row.created_at,
        )
```

- [ ] **Step 3: Сгенерировать миграцию (требуется запущенная БД)**

```bash
uv run alembic revision --autogenerate -m "add device_limit to devices and pending_payments"
```

Ожидаемый вывод: `Detected added column 'devices.device_limit'` и `Detected added column 'pending_payments.device_limit'`, файл создан.

- [ ] **Step 4: Применить миграцию**

```bash
uv run alembic upgrade head
```

Ожидаемый вывод: строка `Running upgrade ... -> <id>, add device_limit to devices and pending_payments`.

- [ ] **Step 5: Запустить тесты — убедиться что ничего не сломалось**

```bash
uv run pytest tests/unit/device/ -v --tb=short
```

Ожидаемый вывод: все тесты device `PASSED` (4 падения в user/ — pre-existing, не наша задача).

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/adapters/orm.py src/apps/device/adapters/gateway.py alembic/versions/
git commit -m "feat: add device_limit column to devices and pending_payments with migration"
```

---

## Task 3: DeviceInteractor — Remnawave-интеграция (TDD)

**Files:**
- Modify: `src/apps/device/application/interactor.py`
- Modify: `src/apps/device/ioc.py`
- Modify: `tests/unit/device/conftest.py`
- Modify: `tests/unit/device/test_device_interactor.py`

- [ ] **Step 1: Написать failing-тесты для Remnawave-интеграции**

Открыть `tests/unit/device/test_device_interactor.py`. Добавить в конец файла (импорты нужны в начале файла):

Добавить в imports в начало файла:
```python
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveUserInfo
```

Добавить в конец файла:

```python
def _make_remnawave_user_info(
    uuid: str = "rw-uuid-123",
    subscription_url: str = "https://sub.test/abc",
    telegram_id: int = 123,
) -> RemnawaveUserInfo:
    return RemnawaveUserInfo(
        uuid=uuid,
        username=f"tg{telegram_id}",
        subscription_url=subscription_url,
        expire_at=datetime.now(UTC) + timedelta(days=30),
        status="ACTIVE",
        hwid_device_limit=1,
        telegram_id=telegram_id,
    )


@pytest.mark.asyncio
async def test_confirm_payment_new_creates_remnawave_user_when_no_uuid(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    """Новый пользователь (remnawave_uuid=None) → create_user вызывается, uuid и url сохраняются."""
    pending = PendingPayment(
        id=5,
        user_telegram_id=123,
        action="new",
        device_type="Android",
        duration=1,
        amount=150,
        balance_to_deduct=0,
        device_limit=1,
        created_at=datetime.now(UTC),
    )
    mock_pending_gateway.get_by_id.return_value = pending
    mock_gateway.get_next_seq.return_value = 1
    user = User(telegram_id=123, balance=0, remnawave_uuid=None, subscription_url=None)
    mock_user_gateway.get_by_telegram_id.return_value = user
    mock_remnawave_gateway.create_user.return_value = _make_remnawave_user_info()

    result = await interactor.confirm_payment(ConfirmPayment(pending_id=5))

    mock_remnawave_gateway.create_user.assert_called_once()
    mock_remnawave_gateway.update_user.assert_not_called()
    assert user.remnawave_uuid == "rw-uuid-123"
    assert user.subscription_url == "https://sub.test/abc"
    assert result.subscription_url == "https://sub.test/abc"
    mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_payment_new_updates_remnawave_user_when_uuid_exists(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    """Существующий Remnawave-пользователь → update_user, не create_user."""
    pending = PendingPayment(
        id=6,
        user_telegram_id=123,
        action="new",
        device_type="iOS",
        duration=3,
        amount=400,
        balance_to_deduct=0,
        device_limit=2,
        created_at=datetime.now(UTC),
    )
    mock_pending_gateway.get_by_id.return_value = pending
    mock_gateway.get_next_seq.return_value = 2
    user = User(
        telegram_id=123,
        balance=0,
        remnawave_uuid="existing-uuid",
        subscription_url="https://sub.test/existing",
    )
    mock_user_gateway.get_by_telegram_id.return_value = user

    result = await interactor.confirm_payment(ConfirmPayment(pending_id=6))

    mock_remnawave_gateway.update_user.assert_called_once()
    mock_remnawave_gateway.create_user.assert_not_called()
    assert result.subscription_url == "https://sub.test/existing"


@pytest.mark.asyncio
async def test_confirm_payment_renew_creates_remnawave_user_for_migration(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    """Старый пользователь продлевает (remnawave_uuid=None) → миграция через create_user."""
    sub = Subscription(
        device_id=1,
        plan=1,
        start_date=datetime.now(UTC),
        end_date=datetime.now(UTC),
    )
    device = Device(id=1, user_id=123, device_name="Android 1", subscription=sub)
    mock_gateway.get_by_name.return_value = device
    pending = PendingPayment(
        id=7,
        user_telegram_id=123,
        action="renew",
        device_name="Android 1",
        device_type="Android",
        duration=1,
        amount=150,
        balance_to_deduct=0,
        device_limit=1,
        created_at=datetime.now(UTC),
    )
    mock_pending_gateway.get_by_id.return_value = pending
    user = User(telegram_id=123, balance=0, remnawave_uuid=None, subscription_url=None)
    mock_user_gateway.get_by_telegram_id.return_value = user
    mock_remnawave_gateway.create_user.return_value = _make_remnawave_user_info(
        uuid="migrated-uuid", subscription_url="https://sub.test/migrated"
    )

    result = await interactor.confirm_payment(ConfirmPayment(pending_id=7))

    mock_remnawave_gateway.create_user.assert_called_once()
    assert result.subscription_url == "https://sub.test/migrated"


@pytest.mark.asyncio
async def test_confirm_payment_renew_updates_remnawave_when_uuid_exists(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    """Продление существующего Remnawave-пользователя → update_user с новым expire_at."""
    sub = Subscription(
        device_id=1,
        plan=1,
        start_date=datetime.now(UTC),
        end_date=datetime.now(UTC),
    )
    device = Device(id=1, user_id=123, device_name="Android 1", subscription=sub)
    mock_gateway.get_by_name.return_value = device
    pending = PendingPayment(
        id=8,
        user_telegram_id=123,
        action="renew",
        device_name="Android 1",
        device_type="Android",
        duration=3,
        amount=400,
        balance_to_deduct=0,
        device_limit=2,
        created_at=datetime.now(UTC),
    )
    mock_pending_gateway.get_by_id.return_value = pending
    user = User(
        telegram_id=123,
        balance=0,
        remnawave_uuid="rw-uuid",
        subscription_url="https://sub.test/url",
    )
    mock_user_gateway.get_by_telegram_id.return_value = user

    result = await interactor.confirm_payment(ConfirmPayment(pending_id=8))

    mock_remnawave_gateway.update_user.assert_called_once()
    call_kwargs = mock_remnawave_gateway.update_user.call_args.kwargs
    assert call_kwargs["uuid"] == "rw-uuid"
    assert call_kwargs["device_limit"] == 2
    assert result.subscription_url == "https://sub.test/url"
```

- [ ] **Step 2: Обновить conftest.py**

Полное содержимое `tests/unit/device/conftest.py`:

```python
import pytest
from unittest.mock import AsyncMock

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
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
def mock_remnawave_gateway() -> AsyncMock:
    return AsyncMock(spec=RemnawaveGateway)


@pytest.fixture
def interactor(
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_uow: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
) -> DeviceInteractor:
    return DeviceInteractor(
        gateway=mock_gateway,
        user_gateway=mock_user_gateway,
        uow=mock_uow,
        pending_gateway=mock_pending_gateway,
        remnawave_gateway=mock_remnawave_gateway,
    )
```

- [ ] **Step 3: Запустить тесты — убедиться что новые падают**

```bash
uv run pytest tests/unit/device/test_device_interactor.py -v --tb=short 2>&1 | tail -20
```

Ожидаемый вывод: новые тесты падают с `TypeError` (interactor ещё не принимает `remnawave_gateway`), старые тесты тоже могут падать из-за изменения conftest.

- [ ] **Step 4: Обновить interactor.py**

Полное содержимое `src/apps/device/application/interactor.py`:

```python
import random
from dataclasses import dataclass
from datetime import UTC, datetime

from dateutil.relativedelta import relativedelta

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
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
    subscription_url: str | None
    end_date: datetime | None


class DeviceInteractor:
    def __init__(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        pending_gateway: PendingPaymentGateway,
        remnawave_gateway: RemnawaveGateway,
    ) -> None:
        self._gateway = gateway
        self._user_gateway = user_gateway
        self._uow = uow
        self._pending_gateway = pending_gateway
        self._remnawave_gateway = remnawave_gateway

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
            device_limit=cmd.device_limit,
            subscription=subscription,
        )
        device.subscription.payments = [payment]  # type: ignore[attr-defined]  # payments not declared in Subscription dataclass, set dynamically before ORM flush

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
        subscription.payments = [Payment(subscription_id=0, amount=0, payment_date=now)]  # type: ignore[attr-defined]  # payments not declared in Subscription dataclass, set dynamically before ORM flush
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
        device.device_limit = cmd.device_limit

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
            device_limit=cmd.device_limit,
            created_at=now,
        )
        saved = await self._pending_gateway.save(pending)
        await self._uow.commit()
        return PendingPaymentInfo(
            id=saved.id,  # type: ignore[arg-type]  # id is set by ORM after save, always int at this point
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
        end_date: datetime

        if pending.action == "new":
            now = datetime.now(UTC)
            end_date = now + relativedelta(months=pending.duration)
            device_name = await self._generate_device_name(pending.device_type)
            await self._save_device(
                CreateDevice(
                    telegram_id=pending.user_telegram_id,
                    device_type=pending.device_type,
                    period_months=pending.duration,
                    amount=pending.amount,
                    balance_to_deduct=pending.balance_to_deduct,
                    device_limit=pending.device_limit,
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
                    device_limit=pending.device_limit,
                )
            )
            device_name = renew_info.device_name
            end_date = renew_info.end_date
        else:
            raise ValueError(f"Unknown pending action: {pending.action}")

        # Remnawave: create or update user
        user = await self._user_gateway.get_by_telegram_id(pending.user_telegram_id)
        if user is None:
            raise UserDeviceNotFound(pending.user_telegram_id)

        if user.remnawave_uuid is None:
            rw_info = await self._remnawave_gateway.create_user(
                telegram_id=pending.user_telegram_id,
                expire_at=end_date,
                device_limit=pending.device_limit,
            )
            user.remnawave_uuid = rw_info.uuid
            user.subscription_url = rw_info.subscription_url
            await self._user_gateway.save(user)
        else:
            await self._remnawave_gateway.update_user(
                uuid=user.remnawave_uuid,
                expire_at=end_date,
                device_limit=pending.device_limit,
            )

        subscription_url = user.subscription_url

        await self._pending_gateway.delete(cmd.pending_id)
        await self._uow.commit()

        return ConfirmPaymentResult(
            user_telegram_id=pending.user_telegram_id,
            device_name=device_name,
            action=pending.action,
            subscription_url=subscription_url,
            end_date=end_date,
        )

    async def _save_device(self, cmd: CreateDevice, device_name: str) -> None:
        user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserDeviceNotFound(cmd.telegram_id)

        now = datetime.now(UTC)
        end_date = now + relativedelta(months=cmd.period_months)
        subscription = Subscription(device_id=0, plan=cmd.period_months, start_date=now, end_date=end_date)
        subscription.payments = [Payment(subscription_id=0, amount=cmd.amount, payment_date=now)]  # type: ignore[attr-defined]  # payments not declared in Subscription dataclass, set dynamically before ORM flush
        device = Device(
            user_id=user.telegram_id,
            device_name=device_name,
            created_at=now,
            vpn_config=cmd.vpn_config,
            vpn_client_uuid=None,
            device_limit=cmd.device_limit,
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
        device.device_limit = cmd.device_limit

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
            id=pending.id,  # type: ignore[arg-type]  # id is set by ORM after gateway lookup, always int at this point
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

- [ ] **Step 5: Обновить ioc.py**

Полное содержимое `src/apps/device/ioc.py`:

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
        remnawave_gateway: RemnawaveGateway,
    ) -> DeviceInteractor:
        return DeviceInteractor(
            gateway=gateway,
            user_gateway=user_gateway,
            uow=uow,
            pending_gateway=pending_gateway,
            remnawave_gateway=remnawave_gateway,
        )
```

- [ ] **Step 6: Обновить существующий test_confirm_payment_new в test_device_interactor.py**

Найти тест `test_confirm_payment_new_creates_device_and_returns_result` и заменить его полностью:

```python
@pytest.mark.asyncio
async def test_confirm_payment_new_creates_device_and_returns_result(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    pending = PendingPayment(
        id=5,
        user_telegram_id=123,
        action="new",
        device_type="Android",
        duration=1,
        amount=150,
        balance_to_deduct=0,
        device_limit=1,
        created_at=datetime.now(UTC),
    )
    mock_pending_gateway.get_by_id.return_value = pending
    mock_gateway.get_next_seq.return_value = 1
    mock_user_gateway.get_by_telegram_id.return_value = User(
        telegram_id=123, balance=0, remnawave_uuid=None, subscription_url=None
    )
    mock_remnawave_gateway.create_user.return_value = _make_remnawave_user_info()

    result = await interactor.confirm_payment(ConfirmPayment(pending_id=5))

    assert result.action == "new"
    assert result.subscription_url == "https://sub.test/abc"
    assert result.user_telegram_id == 123
    mock_pending_gateway.delete.assert_called_once_with(5)
    mock_gateway.save.assert_called_once()
```

- [ ] **Step 7: Запустить тесты device — все должны пройти**

```bash
uv run pytest tests/unit/device/ -v --tb=short
```

Ожидаемый вывод: все тесты `PASSED`.

- [ ] **Step 8: Commit**

```bash
git add src/apps/device/application/interactor.py src/apps/device/ioc.py tests/unit/device/conftest.py tests/unit/device/test_device_interactor.py
git commit -m "feat: integrate RemnawaveGateway into DeviceInteractor, create/update user on confirm_payment"
```

---

## Task 4: Bot keyboards — выбор количества устройств

**Files:**
- Modify: `src/common/bot/cbdata.py`
- Modify: `src/common/bot/keyboards/user_actions.py`
- Modify: `src/common/bot/keyboards/keyboards.py`

- [ ] **Step 1: Добавить device_limit в VpnCallback**

В `src/common/bot/cbdata.py` добавить поле в `VpnCallback`:

```python
class VpnCallback(CallbackData, prefix="vpn"):
    action: VpnAction | None = None
    device: str | None = None
    device_name: str | None = None
    device_limit: int | None = None   # 1, 2 или 3 — выбирается на шаге 1.5
    duration: int | None = 0
    referral_id: int | None = None
    payment: int | None = None
    balance: int | None = None
    choice: ChoiceType | None = None
    payment_status: PaymentStatus | None = None
```

- [ ] **Step 2: Добавить TARIFF_MATRIX в user_actions.py**

В `src/common/bot/keyboards/user_actions.py` после класса `ActualTariff` добавить:

```python
# Цены по матрице (device_limit, months) → цена в рублях
# device_limit: 1, 2 или 3 устройства
TARIFF_MATRIX: dict[int, dict[int, int]] = {
    1: {1: 150,  3: 400,  6: 700,  12: 1200},
    2: {1: 250,  3: 650,  6: 1100, 12: 1900},
    3: {1: 350,  3: 900,  6: 1500, 12: 2600},
}
```

- [ ] **Step 3: Добавить get_keyboard_device_count в keyboards.py**

В `src/common/bot/keyboards/keyboards.py` после импортов добавить импорт если не добавлен:
```python
from src.common.bot.keyboards.user_actions import TARIFF_MATRIX
```

Добавить функцию `get_keyboard_device_count` после `get_keyboard_type_device`:

```python
def get_keyboard_device_count(
    action: str, device: str, referral_id: int | None = None
) -> InlineKeyboardMarkup:
    """Шаг 1.5: выбор количества устройств."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for count, label in [(1, "1 устройство"), (2, "2 устройства"), (3, "3 устройства")]:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=label,
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    device_limit=count,
                    duration=0,
                    referral_id=referral_id,
                ).pack(),
            )
        ])
    return keyboard
```

- [ ] **Step 4: Обновить get_keyboard_tariff — принимать device_limit и показывать правильные цены**

Найти функцию `get_keyboard_tariff` и заменить её сигнатуру и тело:

```python
def get_keyboard_tariff(
    action: str,
    device: str,
    device_limit: int,
    referral_id: int | None = None,
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    prices = TARIFF_MATRIX[device_limit]
    for months, label in [(1, "1 мес"), (3, "3 мес"), (6, "6 мес"), (12, "12 мес")]:
        price = prices[months]
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{label} — {price} руб.",
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    device_limit=device_limit,
                    duration=months,
                    referral_id=referral_id,
                    payment=price,
                ).pack(),
            )
        ])
    return keyboard
```

- [ ] **Step 5: Проверить импорт**

```bash
uv run python -c "from src.common.bot.keyboards.keyboards import get_keyboard_device_count, get_keyboard_tariff; print('OK')"
```

Ожидаемый вывод: `OK`.

- [ ] **Step 6: Commit**

```bash
git add src/common/bot/cbdata.py src/common/bot/keyboards/user_actions.py src/common/bot/keyboards/keyboards.py
git commit -m "feat: add device count selection step to bot keyboards with multi-device pricing"
```

---

## Task 5: Bot router — новый шаг + subscription_url

**Files:**
- Modify: `src/apps/device/controllers/bot/router.py`

- [ ] **Step 1: Обновить импорты в router.py**

Найти строки импортов клавиатур и добавить `get_keyboard_device_count`:

```python
from src.common.bot.keyboards.keyboards import (
    create_inline_kb,
    get_keyboard_admin_confirm,
    get_keyboard_approve_payment_or_cancel,
    get_keyboard_device_count,
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

- [ ] **Step 2: Обновить handle_vpn_flow — добавить шаг 1.5 и передавать device_limit**

В функции `handle_vpn_flow` изменить переменные в начале, добавив `device_limit`:

```python
    action = callback_data.action
    device = callback_data.device
    device_limit = callback_data.device_limit
    duration = callback_data.duration
    referral_id = callback_data.referral_id
    payment = callback_data.payment
    balance = callback_data.balance
    choice = callback_data.choice
    payment_status = callback_data.payment_status
```

После блока "Шаг 1" (после `if device is None`) добавить новый шаг:

```python
    # Шаг 1.5: выбор количества устройств
    if device_limit is None:
        await call.message.edit_text(
            "Выберите количество устройств:",
            reply_markup=get_keyboard_device_count(action=action, device=device, referral_id=referral_id),
        )
        await call.answer()
        return
```

Обновить "Шаг 2" — передавать `device_limit` в `get_keyboard_tariff`:

```python
    # Шаг 2: выбор тарифа
    if duration == 0:
        await call.message.edit_text(
            "Выберете тариф, который хотите подключить:",
            reply_markup=get_keyboard_tariff(
                action=action, device=device, device_limit=device_limit, referral_id=referral_id
            ),
        )
        await call.answer()
        return
```

Обновить сохранение данных в FSM state — добавить `device_limit`:

```python
            await state.set_data(
                {
                    "action": action,
                    "device": device,
                    "device_limit": device_limit,
                    "duration": duration,
                    "referral_id": referral_id,
                    "payment": payment,
                    "balance": balance,
                }
            )
```

Обновить блок `_show_qr_from_state` — передавать `device_limit` в callback при восстановлении из FSM (функция `_show_qr_from_state` использует `get_keyboard_approve_payment_or_cancel`, который передаёт данные дальше через `VpnCallback`). Нужно обновить функцию `_show_qr_from_state`:

```python
async def _show_qr_from_state(
    msg_or_call: types.Message | types.CallbackQuery,
    state: FSMContext,
) -> None:
    """Восстановить данные из FSM state и показать QR."""
    data = await state.get_data()
    await state.clear()

    message = msg_or_call.message if isinstance(msg_or_call, types.CallbackQuery) else msg_or_call

    file_data = await get_photo_for_pay()
    await message.answer_photo(
        photo=file_data,
        caption=bot_repl.get_approve_payment(amount=data["payment"], payment_link=LINK),
        reply_markup=get_keyboard_approve_payment_or_cancel(
            action=data["action"],
            device=data["device"],
            device_limit=data.get("device_limit", 1),
            duration=data["duration"],
            referral_id=data.get("referral_id"),
            payment=data["payment"],
            balance=data["balance"],
            choice=ChoiceType.STOP,
        ),
    )
```

Обновить вызов `_show_qr_payment` — добавить `device_limit` в параметры:

```python
async def _show_qr_payment(
    call: types.CallbackQuery,
    action: str,
    device: str,
    device_limit: int,
    duration: int,
    referral_id: int | None,
    payment: int,
    balance: int,
) -> None:
    """Показать QR-код для оплаты (Step 5)."""
    file_data = await get_photo_for_pay()
    await call.message.answer_photo(
        photo=file_data,
        caption=bot_repl.get_approve_payment(amount=payment, payment_link=LINK),
        reply_markup=get_keyboard_approve_payment_or_cancel(
            action=action,
            device=device,
            device_limit=device_limit,
            duration=duration,
            referral_id=referral_id,
            payment=payment,
            balance=balance,
            choice=ChoiceType.STOP,
        ),
    )
```

Обновить вызов `_show_qr_payment` в "Шаг 5":

```python
        await _show_qr_payment(
            call,
            action,
            device,
            device_limit,
            duration,
            referral_id,
            payment,
            balance,
        )
```

Обновить `CreatePendingPayment` в "Шаг 6a" — добавить `device_limit`:

```python
        pending = await interactor.create_pending_payment(
            CreatePendingPayment(
                user_telegram_id=call.from_user.id,
                action="new",
                device_type=device,
                duration=duration,
                amount=payment,
                balance_to_deduct=balance,
                device_limit=device_limit or 1,
            )
        )
```

Обновить `CreatePendingPayment` в "Шаг 6b" — добавить `device_limit`:

```python
        pending = await interactor.create_pending_payment(
            CreatePendingPayment(
                user_telegram_id=call.from_user.id,
                action="renew",
                device_type=device,
                duration=duration,
                amount=payment,
                balance_to_deduct=balance,
                device_limit=device_limit or 1,
                device_name=device_name_for_renew,
            )
        )
```

- [ ] **Step 3: Проверить что get_keyboard_approve_payment_or_cancel принимает device_limit**

Открыть `src/common/bot/keyboards/keyboards.py`, найти функцию `get_keyboard_approve_payment_or_cancel`. Если она не принимает `device_limit`, добавить параметр и передать его в `VpnCallback`:

```python
def get_keyboard_approve_payment_or_cancel(
    action: str,
    device: str,
    device_limit: int,
    duration: int,
    referral_id: int | None,
    payment: int,
    balance: int,
    choice: ChoiceType,
) -> InlineKeyboardMarkup:
```

Внутри функции в `VpnCallback` добавить `device_limit=device_limit`.

- [ ] **Step 4: Обновить handle_admin_confirm — отправлять subscription_url**

Найти функцию `handle_admin_confirm` и заменить блок отправки результата пользователю:

```python
    if result.subscription_url:
        if result.action == "new":
            await bot.send_message(
                chat_id=result.user_telegram_id,
                text="✅ Оплата подтверждена! Ваша ссылка для подключения 👇",
            )
        else:
            end_str = result.end_date.strftime("%d.%m.%Y") if result.end_date else "—"
            await bot.send_message(
                chat_id=result.user_telegram_id,
                text=f"✅ Подписка продлена до {end_str}. Ваша ссылка для подключения 👇",
            )
        await bot.send_message(
            chat_id=result.user_telegram_id,
            text=f"`{result.subscription_url}`",
            parse_mode="Markdown",
            reply_markup=get_keyboard_vpn_received(),
        )
    else:
        end_str = result.end_date.strftime("%d.%m.%Y") if result.end_date else "—"
        await bot.send_message(
            chat_id=result.user_telegram_id,
            text=f"✅ Оплата подтверждена! Подписка активна до {end_str}.",
            reply_markup=return_start(),
        )
```

- [ ] **Step 5: Проверить импорты бота**

```bash
uv run python -c "from src.apps.device.controllers.bot.router import router; print('OK')"
```

Ожидаемый вывод: `OK`.

- [ ] **Step 6: Запустить все unit-тесты**

```bash
uv run pytest tests/unit/ -v --tb=short 2>&1 | tail -15
```

Ожидаемый вывод: 43+ тестов `PASSED`, 4 pre-existing падения в `user/` не считаются.

- [ ] **Step 7: Commit**

```bash
git add src/apps/device/controllers/bot/router.py src/common/bot/keyboards/keyboards.py
git commit -m "feat: add device count step to bot flow, send subscription_url on payment confirm"
```
