# Payment Endpoints — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `GET /api/v1/tariffs`, `POST /api/v1/payments/initiate`, `POST /api/v1/payments/{id}/confirm`, `GET /api/v1/payments/{id}/status`, `GET /api/v1/payments/history`, and fix `GET /api/v1/users/referral` for web-only users.

**Architecture:** Plan adds a `status` column to `pending_payments` (instead of deleting on confirm) so the frontend can poll for payment result. A new `payments_router.py` contains all payment HTTP endpoints. The `initiate` endpoint reads TARIFF_MATRIX to compute amounts, creates a pending record, and returns a YooKassa URL (or null for balance-only payments). `DeviceView` gets two new read methods for history and status polling.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Dishka, httpx (YooKassa), pytest-asyncio

**Prerequisites:** Plan `2026-05-05-user-id-foundation.md` must be fully executed first. After that plan, the codebase has:
- `PendingPayment.user_id: int` (not `user_telegram_id`)
- `UserPayment.user_id: int`
- `UserSubscription.user_id: int`
- `CreatePendingPayment.user_id: int`
- `UserView.get_balance_by_user_id(user_id)` and `get_referral_code_by_user_id(user_id)`
- `UserGateway.get_by_user_id(user_id)`
- `SubscriptionGateway.get_active_by_user_id(user_id)`
- `ConfirmPaymentResult.user_telegram_id: int | None`

---

## File Map

| Action | File |
|--------|------|
| Create | `alembic/versions/b2c3d4e5f6a7_add_status_to_pending_payments.py` |
| Modify | `src/apps/device/adapters/orm.py` |
| Modify | `src/apps/device/domain/models.py` |
| Modify | `src/apps/device/application/interfaces/pending_gateway.py` |
| Modify | `src/apps/device/adapters/gateway.py` |
| Modify | `src/apps/device/application/interfaces/view.py` |
| Modify | `src/apps/device/adapters/view.py` |
| Modify | `src/apps/device/application/interactor.py` |
| Create | `src/apps/device/controllers/http/tariffs_router.py` |
| Create | `src/apps/device/controllers/http/payments_router.py` |
| Modify | `src/apps/user/domain/commands.py` |
| Modify | `src/apps/user/application/interactor.py` |
| Modify | `src/apps/user/controllers/http/router.py` |
| Modify | `main_web.py` |

---

### Task 1: Migration — add status to pending_payments

**Files:**
- Create: `alembic/versions/b2c3d4e5f6a7_add_status_to_pending_payments.py`

- [ ] **Step 1: Create migration file**

```python
# alembic/versions/b2c3d4e5f6a7_add_status_to_pending_payments.py
"""add status to pending_payments

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'pending_payments',
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            server_default='pending',
        )
    )


def downgrade() -> None:
    op.drop_column('pending_payments', 'status')
```

- [ ] **Step 2: Apply migration**

```bash
cd /Users/mihailabakumov/Desktop/vpn
uv run alembic upgrade head
```

Expected: `Running upgrade a1b2c3d4e5f6 -> b2c3d4e5f6a7, add status to pending_payments`

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/b2c3d4e5f6a7_add_status_to_pending_payments.py
git commit -m "feat: add status column to pending_payments"
```

---

### Task 2: Update PendingPayment model, ORM, and gateway

**Files:**
- Modify: `src/apps/device/domain/models.py`
- Modify: `src/apps/device/adapters/orm.py`
- Modify: `src/apps/device/application/interfaces/pending_gateway.py`
- Modify: `src/apps/device/adapters/gateway.py`

- [ ] **Step 1: Add status to PendingPayment domain model**

In `src/apps/device/domain/models.py`, update the `PendingPayment` dataclass (add `status` field after `id`):

```python
@dataclass
class PendingPayment:
    user_id: int                   # users.id — primary identifier
    action: str                    # "new" | "renew"
    device_type: str
    duration: int                  # месяцев
    amount: int                    # к оплате
    balance_to_deduct: int
    created_at: datetime
    device_name: str | None = None
    device_limit: int = 1
    status: str = "pending"        # "pending" | "confirmed" | "rejected"
    id: int | None = None
```

- [ ] **Step 2: Add status column to PendingPaymentORM**

In `src/apps/device/adapters/orm.py`, update `PendingPaymentORM` — add `status` column after `created_at`:

```python
class PendingPaymentORM(Base):
    __tablename__ = "pending_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    user_telegram_id = Column(BigInteger, nullable=True)  # nullable: legacy + web-only
    action = Column(String(10), nullable=False)  # "new" | "renew"
    device_type = Column(String(20), nullable=False)
    device_name = Column(String(100), nullable=True)  # для renew
    duration = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)
    balance_to_deduct = Column(Integer, nullable=False, default=0)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
```

- [ ] **Step 3: Add update_status to PendingPaymentGateway interface**

Replace `src/apps/device/application/interfaces/pending_gateway.py`:

```python
from typing import Protocol

from src.apps.device.domain.models import PendingPayment


class PendingPaymentGateway(Protocol):
    async def save(self, pending: PendingPayment) -> PendingPayment: ...
    async def get_by_id(self, pending_id: int) -> PendingPayment | None: ...
    async def delete(self, pending_id: int) -> None: ...
    async def update_status(self, pending_id: int, status: str) -> None: ...
```

- [ ] **Step 4: Implement update_status in adapter + update get_by_id to return status**

In `src/apps/device/adapters/gateway.py`, update `SQLAlchemyPendingPaymentGateway`:

Replace the `get_by_id` method body to include `status`:

```python
    async def get_by_id(self, pending_id: int) -> PendingPayment | None:
        result = await self._session.execute(
            select(PendingPaymentORM).where(PendingPaymentORM.id == pending_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return PendingPayment(
            id=row.id,
            user_id=row.user_id,  # type: ignore[arg-type]  # set by ORM after save
            action=row.action,
            device_type=row.device_type,
            device_name=row.device_name,
            duration=row.duration,
            amount=row.amount,
            balance_to_deduct=row.balance_to_deduct,
            device_limit=row.device_limit,
            created_at=row.created_at,
            status=row.status,
        )
```

Add the `update_status` method after `delete`:

```python
    async def update_status(self, pending_id: int, status: str) -> None:
        result = await self._session.execute(
            select(PendingPaymentORM).where(PendingPaymentORM.id == pending_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.status = status
            await self._session.flush()
```

- [ ] **Step 5: Verify no import errors**

```bash
cd /Users/mihailabakumov/Desktop/vpn
uv run python -c "from src.apps.device.adapters.gateway import SQLAlchemyPendingPaymentGateway; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/domain/models.py \
        src/apps/device/adapters/orm.py \
        src/apps/device/application/interfaces/pending_gateway.py \
        src/apps/device/adapters/gateway.py
git commit -m "feat: add status to PendingPayment model, ORM, and gateway"
```

---

### Task 3: Update DeviceInteractor — use update_status instead of delete

**Files:**
- Modify: `src/apps/device/application/interactor.py`

- [ ] **Step 1: Write failing test**

In `tests/unit/device/test_device_interactor.py`, add a test that verifies `confirm_payment` calls `update_status` and NOT `delete`:

```python
async def test_confirm_payment_calls_update_status_not_delete():
    """confirm_payment marks pending as confirmed, does not delete it."""
    mock_pending_gateway = AsyncMock(spec=PendingPaymentGateway)
    mock_pending_gateway.get_by_id.return_value = _make_pending(
        user_id=42, action="new", duration=1, amount=150, balance_to_deduct=0, device_limit=1
    )
    mock_subscription_gateway = AsyncMock(spec=SubscriptionGateway)
    mock_subscription_gateway.save.side_effect = lambda sub: sub
    mock_subscription_gateway.count_payments_for_user.return_value = 0
    mock_subscription_gateway.save_payment.side_effect = lambda p: p

    mock_user = User(telegram_id=111, balance=0)
    mock_user.id = 42
    mock_user.remnawave_uuid = "existing-uuid"
    mock_user.subscription_url = "https://sub.url"
    mock_user_gateway = AsyncMock(spec=UserGateway)
    mock_user_gateway.get_by_user_id.return_value = mock_user

    mock_remnawave = AsyncMock(spec=RemnawaveGateway)
    mock_remnawave.update_user.return_value = RemnawaveUserInfo(
        uuid="existing-uuid", username="tg111",
        subscription_url="https://sub.url",
        expire_at=datetime.now(UTC) + timedelta(days=30),
        status="ACTIVE", hwid_device_limit=1, telegram_id=111,
    )

    interactor = DeviceInteractor(
        gateway=AsyncMock(),
        user_gateway=mock_user_gateway,
        uow=AsyncMock(),
        pending_gateway=mock_pending_gateway,
        remnawave_gateway=mock_remnawave,
        subscription_gateway=mock_subscription_gateway,
    )

    await interactor.confirm_payment(ConfirmPayment(pending_id=1))

    mock_pending_gateway.update_status.assert_called_once_with(1, "confirmed")
    mock_pending_gateway.delete.assert_not_called()
```

Run: `uv run pytest tests/unit/device/test_device_interactor.py::test_confirm_payment_calls_update_status_not_delete -v`

Expected: FAIL (update_status not called yet; delete is still being called)

- [ ] **Step 2: Update confirm_payment in interactor**

In `src/apps/device/application/interactor.py`, find this line in `confirm_payment`:

```python
        await self._pending_gateway.delete(cmd.pending_id)
```

Replace it with:

```python
        await self._pending_gateway.update_status(cmd.pending_id, "confirmed")
```

- [ ] **Step 3: Update reject_payment in interactor**

Find this block in `reject_payment`:

```python
        await self._pending_gateway.delete(cmd.pending_id)
        await self._uow.commit()
        return info
```

Replace with:

```python
        await self._pending_gateway.update_status(cmd.pending_id, "rejected")
        await self._uow.commit()
        return info
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/device/test_device_interactor.py -v
```

Expected: all PASS including the new test

- [ ] **Step 5: Commit**

```bash
git add src/apps/device/application/interactor.py \
        tests/unit/device/test_device_interactor.py
git commit -m "refactor: confirm/reject_payment use update_status instead of delete"
```

---

### Task 4: Add DeviceView methods for payment history and pending status

**Files:**
- Modify: `src/apps/device/application/interfaces/view.py`
- Modify: `src/apps/device/adapters/view.py`

- [ ] **Step 1: Write failing tests**

In `tests/unit/device/test_device_view.py` (create if doesn't exist):

```python
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.apps.device.adapters.view import SQLAlchemyDeviceView


async def test_get_payment_history_returns_empty_for_unknown_user():
    """Returns empty list when no payments found."""
    session = AsyncMock()
    session.execute.return_value = MagicMock(all=MagicMock(return_value=[]))
    view = SQLAlchemyDeviceView(session)
    result = await view.get_payment_history(user_id=999)
    assert result == []


async def test_get_pending_status_returns_none_for_unknown_pending():
    """Returns None when pending not found or not owned by user."""
    session = AsyncMock()
    session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    view = SQLAlchemyDeviceView(session)
    result = await view.get_pending_status(pending_id=999, user_id=42)
    assert result is None
```

Run: `uv run pytest tests/unit/device/test_device_view.py -v`

Expected: FAIL (methods don't exist yet)

- [ ] **Step 2: Add dataclasses and methods to DeviceView interface**

In `src/apps/device/application/interfaces/view.py`, add new dataclasses and extend the Protocol:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class DeviceSummary:
    id: int
    device_name: str


@dataclass(frozen=True)
class DeviceDetailInfo:
    device_name: str
    end_date: str
    amount: int
    payment_date: str


@dataclass(frozen=True)
class SubscriptionInfo:
    end_date: datetime | None
    device_limit: int
    last_payment_amount: int | None
    subscription_url: str | None


@dataclass(frozen=True)
class PaymentHistoryItem:
    id: int
    amount: int
    date: datetime
    plan: int
    device_limit: int
    payment_method: str
    status: str


@dataclass(frozen=True)
class PendingStatusResult:
    status: str                    # "pending" | "confirmed" | "rejected"
    subscription_url: str | None
    end_date: datetime | None


class DeviceView(Protocol):
    async def list_for_user(self, telegram_id: int) -> list[DeviceSummary]: ...

    async def list_for_user_by_id(self, user_id: int) -> list[DeviceSummary]: ...

    async def get_full_info(self, device_id: int) -> DeviceDetailInfo | None: ...

    async def get_subscription_info(self, telegram_id: int) -> SubscriptionInfo | None: ...

    async def get_payment_history(self, user_id: int) -> list[PaymentHistoryItem]: ...

    async def get_pending_status(
        self, pending_id: int, user_id: int
    ) -> PendingStatusResult | None: ...
```

- [ ] **Step 3: Implement get_payment_history in SQLAlchemyDeviceView**

In `src/apps/device/adapters/view.py`, add these imports at the top (update existing import):

```python
from src.apps.device.application.interfaces.view import (
    DeviceDetailInfo,
    DeviceSummary,
    PaymentHistoryItem,
    PendingStatusResult,
    SubscriptionInfo,
)
```

Add also this import:
```python
from src.apps.device.adapters.orm import (
    DeviceORM,
    PaymentORM,
    PendingPaymentORM,
    SubscriptionORM,
    UserPaymentORM,
    UserSubscriptionORM,
)
```

Append `get_payment_history` method to `SQLAlchemyDeviceView`:

```python
    async def get_payment_history(self, user_id: int) -> list[PaymentHistoryItem]:
        result = await self._session.execute(
            select(
                UserPaymentORM.id,
                UserPaymentORM.amount,
                UserPaymentORM.payment_date,
                UserPaymentORM.duration,
                UserPaymentORM.device_limit,
                UserPaymentORM.payment_method,
                UserPaymentORM.status,
            )
            .where(UserPaymentORM.user_id == user_id)
            .order_by(UserPaymentORM.payment_date.desc())
        )
        return [
            PaymentHistoryItem(
                id=row.id,
                amount=row.amount,
                date=row.payment_date,
                plan=row.duration,
                device_limit=row.device_limit,
                payment_method=row.payment_method or "карта",
                status=row.status,
            )
            for row in result.all()
        ]
```

- [ ] **Step 4: Implement get_pending_status in SQLAlchemyDeviceView**

Append `get_pending_status` method to `SQLAlchemyDeviceView`:

```python
    async def get_pending_status(
        self, pending_id: int, user_id: int
    ) -> PendingStatusResult | None:
        # Ownership check + status
        result = await self._session.execute(
            select(PendingPaymentORM.status)
            .where(PendingPaymentORM.id == pending_id)
            .where(PendingPaymentORM.user_id == user_id)
        )
        status = result.scalar_one_or_none()
        if status is None:
            return None  # not found or belongs to different user

        if status in ("pending", "rejected"):
            return PendingStatusResult(status=status, subscription_url=None, end_date=None)

        # status == "confirmed" — look up current subscription data
        url_result = await self._session.execute(
            select(UserORM.subscription_url).where(UserORM.id == user_id)
        )
        subscription_url = url_result.scalar_one_or_none()

        sub_result = await self._session.execute(
            select(UserSubscriptionORM.end_date)
            .where(UserSubscriptionORM.user_id == user_id)
            .where(UserSubscriptionORM.is_active.is_(True))
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        end_date = sub_result.scalar_one_or_none()

        return PendingStatusResult(
            status="confirmed",
            subscription_url=subscription_url,
            end_date=end_date,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/device/test_device_view.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/application/interfaces/view.py \
        src/apps/device/adapters/view.py \
        tests/unit/device/test_device_view.py
git commit -m "feat: add get_payment_history and get_pending_status to DeviceView"
```

---

### Task 5: GET /api/v1/tariffs

**Files:**
- Create: `src/apps/device/controllers/http/tariffs_router.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/device/test_tariffs_router.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from dishka.integrations.fastapi import setup_dishka
from unittest.mock import MagicMock

from src.apps.device.controllers.http.tariffs_router import router


@pytest.fixture
def app():
    _app = FastAPI()
    container = MagicMock()
    container.__aenter__ = MagicMock(return_value=container)
    container.__aexit__ = MagicMock(return_value=None)
    setup_dishka(container, app=_app)
    _app.include_router(router)
    return _app


@pytest.mark.asyncio
async def test_get_tariffs_no_auth(app):
    """GET /api/v1/tariffs returns tariff matrix without authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/tariffs")
    assert resp.status_code == 200
    data = resp.json()
    assert "1" in data
    assert "3" in data["1"]
    assert data["1"]["1"] == 150
    assert data["2"]["3"] == 650
    assert data["3"]["12"] == 2600
```

Run: `uv run pytest tests/unit/device/test_tariffs_router.py -v`

Expected: FAIL (router file doesn't exist)

- [ ] **Step 2: Create tariffs_router.py**

Create `src/apps/device/controllers/http/tariffs_router.py`:

```python
from fastapi import APIRouter

from src.common.bot.keyboards.user_actions import TARIFF_MATRIX

router = APIRouter(prefix="/api/v1", tags=["tariffs"])


@router.get("/tariffs")
async def get_tariffs() -> dict:
    """Тарифная матрица: device_limit → plan_months → price_rub. Без авторизации."""
    return {
        str(device_limit): {
            str(months): price
            for months, price in plans.items()
        }
        for device_limit, plans in TARIFF_MATRIX.items()
    }
```

- [ ] **Step 3: Run test to verify it passes**

```bash
uv run pytest tests/unit/device/test_tariffs_router.py -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/apps/device/controllers/http/tariffs_router.py \
        tests/unit/device/test_tariffs_router.py
git commit -m "feat: GET /api/v1/tariffs endpoint"
```

---

### Task 6: POST /api/v1/payments/initiate

**Files:**
- Create: `src/apps/device/controllers/http/payments_router.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/device/test_payments_router.py`:

```python
import pytest
from datetime import UTC, datetime
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from dishka import Provider, Scope, provide
from dishka.integrations.fastapi import setup_dishka
from unittest.mock import AsyncMock, MagicMock

from src.apps.device.application.interactor import DeviceInteractor, PendingPaymentInfo
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.user.application.interfaces.view import UserView
from src.apps.device.controllers.http.payments_router import router
from src.infrastructure.auth import create_jwt


def _make_jwt(user_id: int = 42) -> str:
    return create_jwt(user_id)


@pytest.fixture
def mock_interactor():
    m = AsyncMock(spec=DeviceInteractor)
    m.create_pending_payment.return_value = PendingPaymentInfo(
        id=1, user_id=42, action="new", device_type="vpn",
        device_name=None, duration=3, amount=300,
    )
    return m


@pytest.fixture
def mock_user_view():
    m = AsyncMock(spec=UserView)
    m.get_balance_by_user_id.return_value = 100
    return m


@pytest.fixture
def mock_device_view():
    return AsyncMock(spec=DeviceView)


@pytest.fixture
def app(mock_interactor, mock_user_view, mock_device_view):
    class MockProvider(Provider):
        scope = Scope.REQUEST

        @provide
        def interactor(self) -> DeviceInteractor:
            return mock_interactor

        @provide
        def user_view(self) -> UserView:
            return mock_user_view

        @provide
        def device_view(self) -> DeviceView:
            return mock_device_view

    _app = FastAPI()
    from dishka import make_async_container
    container = make_async_container(MockProvider())
    setup_dishka(container, app=_app)
    _app.include_router(router)
    return _app


@pytest.mark.asyncio
async def test_initiate_payment_zero_final_amount(app, mock_interactor, mock_user_view):
    """balance covers full amount → payment_url is null."""
    mock_user_view.get_balance_by_user_id.return_value = 999  # more than any tariff
    mock_interactor.create_pending_payment.return_value = PendingPaymentInfo(
        id=5, user_id=42, action="new", device_type="vpn",
        device_name=None, duration=1, amount=0,
    )

    token = _make_jwt(42)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/payments/initiate",
            json={"action": "new", "plan": 1, "device_limit": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_id"] == 5
    assert data["amount"] == 150       # TARIFF_MATRIX[1][1]
    assert data["balance_used"] == 150
    assert data["final_amount"] == 0
    assert data["payment_url"] is None


@pytest.mark.asyncio
async def test_initiate_payment_invalid_plan_returns_422(app):
    """Invalid plan value returns 422."""
    token = _make_jwt(42)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/payments/initiate",
            json={"action": "new", "plan": 99, "device_limit": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 422
```

Run: `uv run pytest tests/unit/device/test_payments_router.py -v`

Expected: FAIL (payments_router.py doesn't exist)

- [ ] **Step 2: Create payments_router.py with initiate endpoint**

Create `src/apps/device/controllers/http/payments_router.py`:

```python
import structlog
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from src.apps.device.application.interactor import DeviceInteractor
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.device.domain.commands import ConfirmPayment, CreatePendingPayment
from src.apps.device.domain.exceptions import PendingPaymentNotFound
from src.apps.user.application.interfaces.view import UserView
from src.common.bot.keyboards.user_actions import TARIFF_MATRIX
from src.infrastructure.auth import CurrentUser
from src.infrastructure.config import app_config
from src.infrastructure.yookassa.client import YooKassaClient

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/payments", tags=["payments"], route_class=DishkaRoute)

_VALID_PLANS = {1, 3, 6, 12}
_VALID_DEVICE_LIMITS = {1, 2, 3}


class InitiatePaymentRequest(BaseModel):
    action: str
    plan: int
    device_limit: int

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("new", "renew"):
            raise ValueError("action must be 'new' or 'renew'")
        return v

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: int) -> int:
        if v not in _VALID_PLANS:
            raise ValueError(f"plan must be one of {sorted(_VALID_PLANS)}")
        return v

    @field_validator("device_limit")
    @classmethod
    def validate_device_limit(cls, v: int) -> int:
        if v not in _VALID_DEVICE_LIMITS:
            raise ValueError(f"device_limit must be one of {sorted(_VALID_DEVICE_LIMITS)}")
        return v


@router.post("/initiate")
async def initiate_payment(
    body: InitiatePaymentRequest,
    user_id: CurrentUser,
    user_view: FromDishka[UserView],
    interactor: FromDishka[DeviceInteractor],
) -> dict:
    full_amount: int = TARIFF_MATRIX[body.device_limit][body.plan]
    balance: int = await user_view.get_balance_by_user_id(user_id)
    balance_used: int = min(balance, full_amount)
    final_amount: int = full_amount - balance_used

    pending = await interactor.create_pending_payment(
        CreatePendingPayment(
            user_id=user_id,
            action=body.action,
            device_type="vpn",
            duration=body.plan,
            amount=final_amount,
            balance_to_deduct=balance_used,
            device_limit=body.device_limit,
        )
    )

    payment_url: str | None = None
    if final_amount > 0:
        if not app_config.yookassa.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service unavailable",
            )
        yookassa_client = YooKassaClient(app_config.yookassa)
        created = await yookassa_client.create_payment(
            amount=final_amount, pending_id=pending.id
        )
        payment_url = created.confirmation_url

    log.info(
        "payment_initiated",
        user_id=user_id,
        pending_id=pending.id,
        action=body.action,
        plan=body.plan,
        full_amount=full_amount,
        balance_used=balance_used,
        final_amount=final_amount,
    )
    return {
        "pending_id": pending.id,
        "amount": full_amount,
        "balance_used": balance_used,
        "final_amount": final_amount,
        "payment_url": payment_url,
    }
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
uv run pytest tests/unit/device/test_payments_router.py::test_initiate_payment_zero_final_amount \
             tests/unit/device/test_payments_router.py::test_initiate_payment_invalid_plan_returns_422 -v
```

Expected: both PASS

- [ ] **Step 4: Commit**

```bash
git add src/apps/device/controllers/http/payments_router.py \
        tests/unit/device/test_payments_router.py
git commit -m "feat: POST /api/v1/payments/initiate endpoint"
```

---

### Task 7: Confirm, status poll, and payment history endpoints

**Files:**
- Modify: `src/apps/device/controllers/http/payments_router.py`

- [ ] **Step 1: Write failing tests**

In `tests/unit/device/test_payments_router.py`, add:

```python
from src.apps.device.application.interfaces.view import PendingStatusResult


@pytest.mark.asyncio
async def test_confirm_payment_not_found_returns_404(app, mock_device_view):
    """Returns 404 when pending_id not found or not owned by user."""
    mock_device_view.get_pending_status.return_value = None
    token = _make_jwt(42)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/payments/999/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_pending_status_pending(app, mock_device_view):
    """Returns status=pending when payment still awaiting."""
    mock_device_view.get_pending_status.return_value = PendingStatusResult(
        status="pending", subscription_url=None, end_date=None
    )
    token = _make_jwt(42)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/payments/1/status",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["subscription_url"] is None
    assert data["end_date"] is None


@pytest.mark.asyncio
async def test_get_payment_history_empty(app, mock_device_view):
    """Returns empty list when no payment history."""
    mock_device_view.get_payment_history.return_value = []
    token = _make_jwt(42)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/payments/history",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json() == []
```

Run: `uv run pytest tests/unit/device/test_payments_router.py -v`

Expected: 3 new tests FAIL (endpoints don't exist)

- [ ] **Step 2: Add confirm, status, and history endpoints to payments_router.py**

Append to `src/apps/device/controllers/http/payments_router.py`:

```python
from src.apps.device.application.interactor import ConfirmPaymentResult  # noqa: F401 (used below)


@router.post("/{pending_id}/confirm")
async def confirm_payment(
    pending_id: int,
    user_id: CurrentUser,
    device_view: FromDishka[DeviceView],
    interactor: FromDishka[DeviceInteractor],
) -> dict:
    pending_status = await device_view.get_pending_status(pending_id, user_id)
    if pending_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    if pending_status.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment already {pending_status.status}",
        )

    try:
        result: ConfirmPaymentResult = await interactor.confirm_payment(
            ConfirmPayment(pending_id=pending_id)
        )
    except PendingPaymentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        ) from exc

    log.info("payment_confirmed_via_api", user_id=user_id, pending_id=pending_id)
    return {
        "subscription_url": result.subscription_url,
        "end_date": result.end_date.isoformat(),
    }


@router.get("/history")
async def get_payment_history(
    user_id: CurrentUser,
    device_view: FromDishka[DeviceView],
) -> list[dict]:
    items = await device_view.get_payment_history(user_id)
    return [
        {
            "id": item.id,
            "amount": item.amount,
            "date": item.date.isoformat(),
            "plan": item.plan,
            "device_limit": item.device_limit,
            "payment_method": item.payment_method,
            "status": item.status,
        }
        for item in items
    ]


@router.get("/{pending_id}/status")
async def get_payment_status(
    pending_id: int,
    user_id: CurrentUser,
    device_view: FromDishka[DeviceView],
) -> dict:
    result = await device_view.get_pending_status(pending_id, user_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return {
        "status": result.status,
        "subscription_url": result.subscription_url,
        "end_date": result.end_date.isoformat() if result.end_date else None,
    }
```

**Important router ordering note:** FastAPI matches routes in declaration order. `/history` must be declared BEFORE `/{pending_id}/status` and `/{pending_id}/confirm` to avoid `history` being captured as a `pending_id`. Verify the order in the file: `POST /initiate` → `POST /{id}/confirm` → `GET /history` → `GET /{id}/status`.

- [ ] **Step 3: Run tests to verify all pass**

```bash
uv run pytest tests/unit/device/test_payments_router.py -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add src/apps/device/controllers/http/payments_router.py \
        tests/unit/device/test_payments_router.py
git commit -m "feat: add confirm, history, and status polling payment endpoints"
```

---

### Task 8: Fix GET /api/v1/users/referral for web-only users

**Files:**
- Modify: `src/apps/user/domain/commands.py`
- Modify: `src/apps/user/application/interactor.py`
- Modify: `src/apps/user/controllers/http/router.py`

- [ ] **Step 1: Write failing test**

In `tests/unit/user/test_user_interactor.py`, add:

```python
async def test_get_referral_code_by_user_id_generates_for_web_only():
    """Web-only user (no telegram_id) gets referral code based on user_id."""
    import hashlib

    web_user = User(telegram_id=None, balance=0)
    web_user.id = 55
    web_user.referral_code = None

    mock_gateway = AsyncMock(spec=UserGateway)
    mock_gateway.get_by_user_id.return_value = web_user
    mock_uow = AsyncMock()

    interactor = UserInteractor(gateway=mock_gateway, uow=mock_uow)
    result = await interactor.get_referral_code_by_user_id(
        GetReferralCodeByUserId(user_id=55)
    )

    expected_code = hashlib.md5(b"55").hexdigest()[:8]
    assert result.referral_code == expected_code
    assert result.telegram_id is None
    mock_gateway.save.assert_called_once()
    mock_uow.commit.assert_called_once()
```

Run: `uv run pytest tests/unit/user/test_user_interactor.py -v`

Expected: FAIL (`GetReferralCodeByUserId` and `get_referral_code_by_user_id` don't exist)

- [ ] **Step 2: Add GetReferralCodeByUserId command**

In `src/apps/user/domain/commands.py`, add after `GetReferralCode`:

```python
@dataclass(frozen=True)
class GetReferralCodeByUserId:
    user_id: int
```

- [ ] **Step 3: Update ReferralCodeInfo to allow nullable telegram_id**

In `src/apps/user/application/interactor.py`, update the `ReferralCodeInfo` dataclass:

```python
@dataclass(frozen=True)
class ReferralCodeInfo:
    telegram_id: int | None     # None for web-only users
    referral_code: str
```

- [ ] **Step 4: Add get_referral_code_by_user_id method to UserInteractor**

In `src/apps/user/application/interactor.py`, add this import at the top (with other commands):

```python
from src.apps.user.domain.commands import (
    AddReferralBonus,
    DeductUserBalance,
    GetOrCreateUser,
    GetReferralCode,
    GetReferralCodeByUserId,
    MarkFreeMonthUsed,
    SetUserEmail,
)
```

Append to `UserInteractor` class after `get_referral_code`:

```python
    async def get_referral_code_by_user_id(
        self, cmd: GetReferralCodeByUserId
    ) -> ReferralCodeInfo:
        user = await self._gateway.get_by_user_id(cmd.user_id)
        if user is None:
            raise UserNotFound(cmd.user_id)

        if user.referral_code is None:
            # Use telegram_id as seed for Telegram users, user_id for web-only
            seed = user.telegram_id if user.telegram_id is not None else cmd.user_id
            user.referral_code = hashlib.md5(str(seed).encode()).hexdigest()[:8]
            await self._gateway.save(user)
            await self._uow.commit()

        return ReferralCodeInfo(
            telegram_id=user.telegram_id,
            referral_code=user.referral_code,  # type: ignore[arg-type]
        )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/unit/user/test_user_interactor.py -v
```

Expected: all PASS including the new test

- [ ] **Step 6: Update HTTP referral endpoint for web-only support**

Replace the `get_referral` function in `src/apps/user/controllers/http/router.py`:

```python
@router.get("/referral")
async def get_referral(
    user_id: CurrentUser,
    user_view: FromDishka[UserView],
    interactor: FromDishka[UserInteractor],
) -> dict:
    result = await interactor.get_referral_code_by_user_id(
        GetReferralCodeByUserId(user_id=user_id)
    )
    telegram_id = await user_view.get_telegram_id(user_id)
    invited_count = 0
    if telegram_id is not None:
        invited_count = await user_view.get_device_count(telegram_id)
    return {
        "referral_code": result.referral_code,
        "referral_link": f"https://t.me/my7vpnbot?start={result.referral_code}",
        "invited_count": invited_count,
    }
```

Also update the import in `src/apps/user/controllers/http/router.py`:

```python
from src.apps.user.domain.commands import GetOrCreateUser, GetReferralCode, GetReferralCodeByUserId
```

- [ ] **Step 7: Commit**

```bash
git add src/apps/user/domain/commands.py \
        src/apps/user/application/interactor.py \
        src/apps/user/controllers/http/router.py \
        tests/unit/user/test_user_interactor.py
git commit -m "feat: referral endpoint works for web-only users (no Telegram required)"
```

---

### Task 9: Register routers + final verification

**Files:**
- Modify: `main_web.py`

- [ ] **Step 1: Register new routers in main_web.py**

In `main_web.py`, add imports after existing router imports:

```python
from src.apps.device.controllers.http.tariffs_router import router as tariffs_router
from src.apps.device.controllers.http.payments_router import router as payments_router
```

Then add `include_router` calls after the existing ones:

```python
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(device_router)
app.include_router(yookassa_router)
app.include_router(cabinet_router)
app.include_router(tariffs_router)
app.include_router(payments_router)
```

- [ ] **Step 2: Verify the app starts without errors**

```bash
cd /Users/mihailabakumov/Desktop/vpn
uv run python -c "from main_web import app; print('routes:', len(app.routes))"
```

Expected: prints route count without ImportError or other errors

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/unit/ -v --tb=short
```

Expected: all PASS

- [ ] **Step 4: Lint and format**

```bash
uv run ruff check --fix && uv run ruff format
```

Expected: no errors

- [ ] **Step 5: Verify API map against spec**

Run a quick route enumeration to confirm all new endpoints are registered:

```bash
uv run python -c "
from main_web import app
routes = [(r.methods, r.path) for r in app.routes if hasattr(r, 'methods')]
for methods, path in sorted(routes, key=lambda x: x[1]):
    print(methods, path)
"
```

Confirm these routes appear:
- `{'GET'}` `/api/v1/tariffs`
- `{'POST'}` `/api/v1/payments/initiate`
- `{'POST'}` `/api/v1/payments/{pending_id}/confirm`
- `{'GET'}` `/api/v1/payments/history`
- `{'GET'}` `/api/v1/payments/{pending_id}/status`

- [ ] **Step 6: Final commit**

```bash
git add main_web.py
git commit -m "feat: register tariffs_router and payments_router in main_web"
```

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|-----------------|------|
| `GET /api/v1/tariffs` — no auth, returns matrix | Task 5 |
| `POST /api/v1/payments/initiate` — JWT, returns pending_id + payment_url | Task 6 |
| `POST /api/v1/payments/{id}/confirm` — JWT, zero-payment confirmation | Task 7 |
| `GET /api/v1/payments/{id}/status` — JWT, polling | Task 7 |
| `GET /api/v1/payments/history` — JWT, payment history | Task 7 |
| Fix `GET /api/v1/users/referral` for web-only | Task 8 |
| `balance_used = min(user.balance, amount)` in initiate | Task 6 |
| `payment_url = null` when `final_amount == 0` | Task 6 |
| `status: "pending" | "confirmed" | "rejected"` in status polling | Tasks 1–4, 7 |
| History reads from `user_payments WHERE user_id = current_user` DESC by date | Task 4 |
| Referral code from `md5(str(user_id))[:8]` for web-only | Task 8 |

### Route Order Warning

FastAPI matches routes in order of declaration. In `payments_router.py`, `GET /history` is a static path that would match the `/{pending_id}/status` pattern if declared after it. The correct declaration order in the file is:

1. `POST /initiate`
2. `POST /{pending_id}/confirm`
3. `GET /history`          ← must come BEFORE `/{pending_id}/status`
4. `GET /{pending_id}/status`

This is handled in Task 7 Step 2 — verify the order when implementing.

### Type Consistency

- `PendingPaymentInfo.user_id: int` — defined in Plan 1 Task 8, used in Task 6 ✅
- `ConfirmPaymentResult` — Plan 1 Task 8 defines `user_telegram_id: int | None` ✅
- `ReferralCodeInfo.telegram_id: int | None` — updated in Task 8 Step 3 ✅
- `PaymentHistoryItem` and `PendingStatusResult` — defined in Task 4 Step 2, used in Tasks 6–7 ✅
- `DeviceView.get_payment_history` and `get_pending_status` — defined in Task 4 interface, used in Task 7 ✅
