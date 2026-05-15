# user_id Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `telegram_id` as primary identifier in domain/application/adapter layers with `user_id` (int PK of `users` table), enabling web-only users to purchase and renew subscriptions.

**Architecture:** Domain models `PendingPayment`, `UserSubscription`, `UserPayment` switch from `user_telegram_id` to `user_id`. DB migration adds `user_id` FK to two tables. Interactors use `get_by_user_id`. Bot controllers resolve `telegram_id → user_id` at entry. HTTP controllers already have `user_id` from JWT — minimal changes.

**Tech Stack:** Python 3.12, SQLAlchemy 2 async, Alembic, Aiogram 3, Dishka, pytest-asyncio

**Prerequisites:** Plan 2 (new payment endpoints) must run AFTER this plan is complete.

---

## File Map

| Action | File |
|--------|------|
| Create | `alembic/versions/a1b2c3d4e5f6_add_user_id_to_payment_tables.py` |
| Modify | `src/apps/device/adapters/orm.py` |
| Modify | `src/apps/device/domain/models.py` |
| Modify | `src/apps/device/domain/commands.py` |
| Modify | `src/apps/device/application/interactor.py` |
| Modify | `src/apps/device/application/interfaces/subscription_gateway.py` |
| Modify | `src/apps/device/application/interfaces/remnawave_gateway.py` |
| Modify | `src/apps/device/adapters/gateway.py` |
| Modify | `src/apps/device/adapters/remnawave_gateway.py` |
| Modify | `src/apps/user/application/interfaces/gateway.py` |
| Modify | `src/apps/user/adapters/gateway.py` |
| Modify | `src/infrastructure/remnawave/client.py` |
| Modify | `src/apps/device/controllers/bot/router.py` |
| Modify | `src/apps/device/controllers/http/yookassa_router.py` |
| Modify | `src/apps/user/controllers/http/router.py` |
| Modify | `src/apps/auth/application/interactor.py` |
| Modify | `tests/unit/device/test_device_interactor.py` |
| Modify | `tests/unit/device/test_subscription_gateway.py` |
| Modify | `tests/unit/device/test_remnawave_gateway.py` |
| Modify | `tests/unit/infrastructure/test_remnawave_client.py` |

---

### Task 1: DB Migration

**Files:**
- Create: `alembic/versions/a1b2c3d4e5f6_add_user_id_to_payment_tables.py`

- [ ] **Step 1: Create migration file**

```python
# alembic/versions/a1b2c3d4e5f6_add_user_id_to_payment_tables.py
"""add user_id to user_payments and pending_payments

Revision ID: a1b2c3d4e5f6
Revises: f1e2d3c4b5a6
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f1e2d3c4b5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user_payments: add user_id FK, make user_telegram_id nullable, backfill
    op.add_column(
        'user_payments',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    )
    op.execute(
        "UPDATE user_payments up SET user_id = u.id FROM users u WHERE u.telegram_id = up.user_telegram_id"
    )
    op.alter_column('user_payments', 'user_telegram_id', nullable=True)
    op.create_index('ix_user_payments_user_id', 'user_payments', ['user_id'])

    # pending_payments: add user_id FK, make user_telegram_id nullable, backfill
    op.add_column(
        'pending_payments',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    )
    op.execute(
        "UPDATE pending_payments pp SET user_id = u.id FROM users u WHERE u.telegram_id = pp.user_telegram_id"
    )
    op.alter_column('pending_payments', 'user_telegram_id', nullable=True)


def downgrade() -> None:
    op.drop_index('ix_user_payments_user_id', table_name='user_payments')
    op.drop_column('user_payments', 'user_id')
    op.alter_column('user_payments', 'user_telegram_id', nullable=False)
    op.drop_column('pending_payments', 'user_id')
    op.alter_column('pending_payments', 'user_telegram_id', nullable=False)
```

- [ ] **Step 2: Apply migration**

```bash
cd /Users/mihailabakumov/Desktop/vpn
uv run alembic upgrade head
```

Expected: `Running upgrade f1e2d3c4b5a6 -> a1b2c3d4e5f6, add user_id to user_payments and pending_payments`

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/a1b2c3d4e5f6_add_user_id_to_payment_tables.py
git commit -m "feat: add user_id FK to user_payments and pending_payments"
```

---

### Task 2: Update ORM Models

**Files:**
- Modify: `src/apps/device/adapters/orm.py`

- [ ] **Step 1: Add user_id columns to UserPaymentORM and PendingPaymentORM**

In `src/apps/device/adapters/orm.py`, change `PendingPaymentORM`:

```python
class PendingPaymentORM(Base):
    __tablename__ = "pending_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    user_telegram_id = Column(BigInteger, nullable=True)  # nullable: legacy + web-only
    action = Column(String(10), nullable=False)
    device_type = Column(String(20), nullable=False)
    device_name = Column(String(100), nullable=True)
    duration = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)
    balance_to_deduct = Column(Integer, nullable=False, default=0)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False)
```

Change `UserPaymentORM`:

```python
class UserPaymentORM(Base):
    __tablename__ = "user_payments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    user_telegram_id = Column(BigInteger, nullable=True, index=True)  # nullable: legacy + web-only
    subscription_id = Column(
        Integer, ForeignKey("user_subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    amount = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    payment_date = Column(DateTime(timezone=True), nullable=False)
    currency = Column(String, default="RUB")
    payment_method = Column(String, default="карта", nullable=True)
    status = Column(String(20), nullable=False, default="success", server_default="success")
    external_id = Column(String, nullable=True)

    subscription = relationship("UserSubscriptionORM", back_populates="payments")
```

- [ ] **Step 2: Verify no import errors**

```bash
cd /Users/mihailabakumov/Desktop/vpn
uv run python -c "from src.apps.device.adapters.orm import PendingPaymentORM, UserPaymentORM; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/apps/device/adapters/orm.py
git commit -m "feat: add user_id FK columns to ORM models"
```

---

### Task 3: Update Domain Models

**Files:**
- Modify: `src/apps/device/domain/models.py`

- [ ] **Step 1: Write failing test**

In `tests/unit/device/test_device_interactor.py`, find `_make_user_subscription` and `_make_pending_payment` helpers. They will fail after domain model change.

Run current tests to capture baseline:

```bash
cd /Users/mihailabakumov/Desktop/vpn
uv run pytest tests/unit/device/test_device_interactor.py -v --tb=short 2>&1 | tail -20
```

Expected: some tests pass (capture count for comparison after change).

- [ ] **Step 2: Change domain models**

Replace `src/apps/device/domain/models.py` with:

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
    user_id: int                   # users.id — primary identifier
    action: str                    # "new" | "renew"
    device_type: str
    duration: int                  # месяцев
    amount: int                    # к оплате
    balance_to_deduct: int
    created_at: datetime
    device_name: str | None = None
    device_limit: int = 1
    id: int | None = None


@dataclass
class UserSubscription:
    user_id: int                   # users.id — primary identifier
    plan: int
    start_date: datetime
    end_date: datetime
    device_limit: int = 1
    is_active: bool = True
    id: int | None = None


@dataclass
class UserPayment:
    user_id: int                   # users.id — primary identifier
    amount: int
    duration: int
    device_limit: int
    payment_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    subscription_id: int | None = None
    currency: str = "RUB"
    payment_method: str = "карта"
    status: str = "success"
    external_id: str | None = None
    id: int | None = None
```

- [ ] **Step 3: Commit**

```bash
git add src/apps/device/domain/models.py
git commit -m "refactor: replace user_telegram_id with user_id in domain models"
```

---

### Task 4: Update Commands

**Files:**
- Modify: `src/apps/device/domain/commands.py`

- [ ] **Step 1: Update CreatePendingPayment and CreateDeviceFree**

Replace `src/apps/device/domain/commands.py` with:

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
    user_id: int               # users.id
    device_type: str
    period_days: int
    device_limit: int = 1


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
class CreatePendingPayment:
    user_id: int               # users.id
    action: str                # "new" | "renew"
    device_type: str
    duration: int
    amount: int
    balance_to_deduct: int
    device_limit: int = 1
    device_name: str | None = None


@dataclass(frozen=True)
class ConfirmPayment:
    pending_id: int


@dataclass(frozen=True)
class RejectPayment:
    pending_id: int


@dataclass(frozen=True)
class MigrateUser:
    telegram_id: int
```

- [ ] **Step 2: Commit**

```bash
git add src/apps/device/domain/commands.py
git commit -m "refactor: CreatePendingPayment and CreateDeviceFree use user_id"
```

---

### Task 5: Update UserGateway — add get_by_user_id

**Files:**
- Modify: `src/apps/user/application/interfaces/gateway.py`
- Modify: `src/apps/user/adapters/gateway.py`

- [ ] **Step 1: Add method to interface**

Replace `src/apps/user/application/interfaces/gateway.py` with:

```python
from typing import Protocol

from src.apps.user.domain.models import User


class UserGateway(Protocol):
    async def get_by_telegram_id(self, telegram_id: int) -> User | None: ...

    async def get_by_user_id(self, user_id: int) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_referral_code(self, referral_code: str) -> User | None: ...

    async def save(self, user: User) -> None: ...
```

- [ ] **Step 2: Implement in adapter**

Add method to `SQLAlchemyUserGateway` in `src/apps/user/adapters/gateway.py` after `get_by_telegram_id`:

```python
    async def get_by_user_id(self, user_id: int) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)
```

- [ ] **Step 3: Verify**

```bash
uv run python -c "from src.apps.user.adapters.gateway import SQLAlchemyUserGateway; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/apps/user/application/interfaces/gateway.py src/apps/user/adapters/gateway.py
git commit -m "feat: add get_by_user_id to UserGateway"
```

---

### Task 6: Update SubscriptionGateway + PendingPaymentGateway

**Files:**
- Modify: `src/apps/device/application/interfaces/subscription_gateway.py`
- Modify: `src/apps/device/adapters/gateway.py`

- [ ] **Step 1: Update SubscriptionGateway interface**

Replace `src/apps/device/application/interfaces/subscription_gateway.py`:

```python
from typing import Protocol

from src.apps.device.domain.models import UserPayment, UserSubscription


class SubscriptionGateway(Protocol):
    async def get_active_by_telegram_id(self, telegram_id: int) -> UserSubscription | None:
        """Legacy lookup for bot/migration flows where telegram_id is available."""
        ...

    async def get_active_by_user_id(self, user_id: int) -> UserSubscription | None:
        """Primary lookup by users.id — works for all user types."""
        ...

    async def save(self, sub: UserSubscription) -> UserSubscription: ...

    async def save_payment(self, payment: UserPayment) -> UserPayment: ...

    async def count_payments_for_user(self, user_id: int) -> int:
        """Count paid (amount > 0) UserPayment records for the user by user_id."""
        ...
```

- [ ] **Step 2: Update SubscriptionGateway adapter**

In `src/apps/device/adapters/gateway.py`, replace the `SQLAlchemySubscriptionGateway` class:

```python
class SQLAlchemySubscriptionGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_by_telegram_id(self, telegram_id: int) -> UserSubscription | None:
        result = await self._session.execute(
            select(UserSubscriptionORM)
            .join(UserORM, UserSubscriptionORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id)
            .where(UserSubscriptionORM.is_active.is_(True))
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UserSubscription(
            id=row.id,
            user_id=row.user_id,
            plan=row.plan,
            start_date=row.start_date,
            end_date=row.end_date,
            device_limit=row.device_limit,
            is_active=row.is_active,
        )

    async def get_active_by_user_id(self, user_id: int) -> UserSubscription | None:
        result = await self._session.execute(
            select(UserSubscriptionORM)
            .where(UserSubscriptionORM.user_id == user_id)
            .where(UserSubscriptionORM.is_active.is_(True))
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UserSubscription(
            id=row.id,
            user_id=row.user_id,
            plan=row.plan,
            start_date=row.start_date,
            end_date=row.end_date,
            device_limit=row.device_limit,
            is_active=row.is_active,
        )

    async def save(self, sub: UserSubscription) -> UserSubscription:
        if sub.id is None:
            orm = UserSubscriptionORM(
                user_id=sub.user_id,   # direct FK — no telegram lookup
                plan=sub.plan,
                start_date=sub.start_date,
                end_date=sub.end_date,
                device_limit=sub.device_limit,
                is_active=sub.is_active,
            )
            self._session.add(orm)
            await self._session.flush()
            sub.id = orm.id
        else:
            result = await self._session.execute(
                select(UserSubscriptionORM).where(UserSubscriptionORM.id == sub.id)
            )
            orm = result.scalar_one()
            orm.end_date = sub.end_date
            orm.device_limit = sub.device_limit
            orm.plan = sub.plan
            orm.start_date = sub.start_date
            await self._session.flush()
        return sub

    async def save_payment(self, payment: UserPayment) -> UserPayment:
        orm = UserPaymentORM(
            user_id=payment.user_id,
            subscription_id=payment.subscription_id,
            amount=payment.amount,
            duration=payment.duration,
            device_limit=payment.device_limit,
            payment_date=payment.payment_date,
            currency=payment.currency,
            payment_method=payment.payment_method,
            status=payment.status,
            external_id=payment.external_id,
        )
        self._session.add(orm)
        await self._session.flush()
        payment.id = orm.id  # type: ignore[misc]
        return payment

    async def count_payments_for_user(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count(UserPaymentORM.id))
            .where(UserPaymentORM.user_id == user_id)
            .where(UserPaymentORM.amount > 0)
        )
        return result.scalar_one()
```

- [ ] **Step 3: Update PendingPaymentGateway adapter**

In `src/apps/device/adapters/gateway.py`, replace `SQLAlchemyPendingPaymentGateway.save` and `get_by_id`:

```python
class SQLAlchemyPendingPaymentGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, pending: PendingPayment) -> PendingPayment:
        if pending.id is None:
            orm = PendingPaymentORM(
                user_id=pending.user_id,
                action=pending.action,
                device_type=pending.device_type,
                device_name=pending.device_name,
                duration=pending.duration,
                amount=pending.amount,
                balance_to_deduct=pending.balance_to_deduct,
                device_limit=pending.device_limit,
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
            user_id=row.user_id,  # type: ignore[arg-type]  # set by ORM after save
            action=row.action,
            device_type=row.device_type,
            device_name=row.device_name,
            duration=row.duration,
            amount=row.amount,
            balance_to_deduct=row.balance_to_deduct,
            device_limit=row.device_limit,
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

- [ ] **Step 4: Commit**

```bash
git add src/apps/device/application/interfaces/subscription_gateway.py src/apps/device/adapters/gateway.py
git commit -m "refactor: subscription/pending gateways use user_id as primary key"
```

---

### Task 7: Update Remnawave — optional telegram_id

**Files:**
- Modify: `src/apps/device/application/interfaces/remnawave_gateway.py`
- Modify: `src/apps/device/adapters/remnawave_gateway.py`
- Modify: `src/infrastructure/remnawave/client.py`

- [ ] **Step 1: Write failing test**

In `tests/unit/infrastructure/test_remnawave_client.py`, add test for web-only user creation:

```python
async def test_create_user_web_only(httpx_mock):
    """create_user with telegram_id=None uses 'web{user_id}' username."""
    httpx_mock.add_response(
        method="POST",
        url="http://remna.test/api/users",
        json={"response": {
            "uuid": "abc-123",
            "username": "web42",
            "subscriptionUrl": "https://sub.url/web42",
            "expireAt": "2026-06-01T00:00:00.000Z",
            "status": "ACTIVE",
            "hwidDeviceLimit": 1,
            "telegramId": None,
        }},
    )
    settings = RemnawaveSettings(url="http://remna.test", token="test", default_squad_uuid=None)
    client = RemnawaveClient(settings)
    result = await client.create_user(
        user_id=42,
        expire_at=datetime(2026, 6, 1, tzinfo=UTC),
        device_limit=1,
        telegram_id=None,
    )
    assert result.username == "web42"
    assert result.telegram_id is None
```

Run: `uv run pytest tests/unit/infrastructure/test_remnawave_client.py -v`
Expected: FAIL (create_user doesn't have user_id param yet)

- [ ] **Step 2: Update RemnawaveGateway interface**

Replace `src/apps/device/application/interfaces/remnawave_gateway.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class HwidDevice:
    hwid: str
    platform: str | None
    os_version: str | None
    device_model: str | None
    created_at: datetime


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
        self,
        user_id: int,
        expire_at: datetime,
        device_limit: int,
        telegram_id: int | None = None,
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

    async def get_hwid_devices_count(self, uuid: str) -> int: ...

    async def get_hwid_devices(self, uuid: str) -> list[HwidDevice]: ...

    async def delete_hwid_device(self, uuid: str, hwid: str) -> None: ...

    async def delete_all_hwid_devices(self, uuid: str) -> None: ...
```

- [ ] **Step 3: Update RemnawaveClient**

In `src/infrastructure/remnawave/client.py`, replace `create_user` method:

```python
    async def create_user(
        self,
        user_id: int,
        expire_at: datetime,
        device_limit: int,
        telegram_id: int | None = None,
    ) -> RemnawaveApiUser:
        username = f"tg{telegram_id}" if telegram_id is not None else f"web{user_id}"
        payload: dict[str, object] = {
            "username": username,
            "expireAt": expire_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "hwidDeviceLimit": device_limit,
            "trafficLimitBytes": 0,
        }
        if telegram_id is not None:
            payload["telegramId"] = telegram_id
        if self._settings.default_squad_uuid:
            payload["activeInternalSquads"] = [self._settings.default_squad_uuid]
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.post("/api/users", json=payload, headers=self._headers())
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
            data = resp.json()["response"]
        log.info("remnawave_user_created", user_id=user_id, telegram_id=telegram_id, uuid=data["uuid"])
        return self._parse_user(data)
```

- [ ] **Step 4: Update RemnawaveGatewayImpl adapter**

In `src/apps/device/adapters/remnawave_gateway.py`, replace `create_user` method:

```python
    async def create_user(
        self,
        user_id: int,
        expire_at: datetime,
        device_limit: int,
        telegram_id: int | None = None,
    ) -> RemnawaveUserInfo:
        raw = await self._client.create_user(
            user_id=user_id,
            expire_at=expire_at,
            device_limit=device_limit,
            telegram_id=telegram_id,
        )
        return self._map(raw)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/unit/infrastructure/test_remnawave_client.py -v
```

Expected: all tests PASS including `test_create_user_web_only`

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/application/interfaces/remnawave_gateway.py \
        src/apps/device/adapters/remnawave_gateway.py \
        src/infrastructure/remnawave/client.py \
        tests/unit/infrastructure/test_remnawave_client.py
git commit -m "feat: remnawave create_user accepts optional telegram_id, uses user_id for username"
```

---

### Task 8: Update DeviceInteractor

**Files:**
- Modify: `src/apps/device/application/interactor.py`

- [ ] **Step 1: Update result dataclasses**

In `src/apps/device/application/interactor.py`, change these dataclasses:

```python
@dataclass(frozen=True)
class PendingPaymentInfo:
    id: int
    user_id: int          # was user_telegram_id
    action: str
    device_type: str
    device_name: str | None
    duration: int
    amount: int


@dataclass(frozen=True)
class ConfirmPaymentResult:
    user_telegram_id: int | None   # None for web-only; used by bot notifications
    device_name: str
    action: str
    subscription_url: str | None
    end_date: datetime
    amount: int = 0
    duration: int = 0
    device_limit: int = 1
    referrer_telegram_id: int | None = None


@dataclass(frozen=True)
class FreeSubscriptionInfo:
    user_id: int          # was user_telegram_id
    subscription_url: str
    end_date: datetime
```

- [ ] **Step 2: Update create_pending_payment**

Replace `create_pending_payment` method body:

```python
    async def create_pending_payment(self, cmd: CreatePendingPayment) -> PendingPaymentInfo:
        now = datetime.now(UTC)
        pending = PendingPayment(
            user_id=cmd.user_id,
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
            id=saved.id,  # type: ignore[arg-type]
            user_id=saved.user_id,
            action=saved.action,
            device_type=saved.device_type,
            device_name=saved.device_name,
            duration=saved.duration,
            amount=saved.amount,
        )
```

- [ ] **Step 3: Update create_device_free**

Replace `create_device_free` method body:

```python
    async def create_device_free(self, cmd: CreateDeviceFree) -> FreeSubscriptionInfo:
        user = await self._user_gateway.get_by_user_id(cmd.user_id)
        if user is None:
            raise UserDeviceNotFound(cmd.user_id)

        now = datetime.now(UTC)
        end_date = now + relativedelta(days=cmd.period_days)

        if user.remnawave_uuid is None:
            rw_info = await self._remnawave_gateway.create_user(
                user_id=cmd.user_id,
                telegram_id=user.telegram_id,
                expire_at=end_date,
                device_limit=cmd.device_limit,
            )
            user.remnawave_uuid = rw_info.uuid
            user.subscription_url = rw_info.subscription_url
        else:
            await self._remnawave_gateway.update_user(
                uuid=user.remnawave_uuid,
                expire_at=end_date,
                device_limit=cmd.device_limit,
            )
            if user.subscription_url is None:
                raise ValueError(f"User {cmd.user_id} has remnawave_uuid but no subscription_url")

        await self._user_gateway.save(user)

        user_sub = UserSubscription(
            user_id=cmd.user_id,
            plan=cmd.period_days,
            start_date=now,
            end_date=end_date,
            device_limit=cmd.device_limit,
        )
        user_sub = await self._subscription_gateway.save(user_sub)

        payment = UserPayment(
            user_id=cmd.user_id,
            subscription_id=user_sub.id,
            amount=0,
            duration=cmd.period_days,
            device_limit=cmd.device_limit,
            payment_method="реферал",
        )
        await self._subscription_gateway.save_payment(payment)
        await self._uow.commit()

        return FreeSubscriptionInfo(
            user_id=cmd.user_id,
            subscription_url=user.subscription_url,  # type: ignore[arg-type]
            end_date=end_date,
        )
```

- [ ] **Step 4: Update confirm_payment — critical changes**

Replace `confirm_payment` method body:

```python
    async def confirm_payment(self, cmd: ConfirmPayment) -> ConfirmPaymentResult:
        pending = await self._pending_gateway.get_by_id(cmd.pending_id)
        if pending is None:
            raise PendingPaymentNotFound(cmd.pending_id)

        now = datetime.now(UTC)
        end_date: datetime
        user_sub: UserSubscription | None = None

        if pending.action == "new":
            end_date = now + relativedelta(months=pending.duration)
            user_sub = UserSubscription(
                user_id=pending.user_id,
                plan=pending.duration,
                start_date=now,
                end_date=end_date,
                device_limit=pending.device_limit,
            )
            user_sub = await self._subscription_gateway.save(user_sub)

        elif pending.action == "renew":
            # Новая модель: ищем UserSubscription по user_id
            user_sub = await self._subscription_gateway.get_active_by_user_id(pending.user_id)
            if user_sub is not None:
                base = user_sub.end_date if user_sub.end_date > now else now
                user_sub.end_date = base + relativedelta(months=pending.duration)
                user_sub.plan = pending.duration
                user_sub.device_limit = pending.device_limit
                user_sub = await self._subscription_gateway.save(user_sub)
                end_date = user_sub.end_date
            else:
                # Легаси: ищем Device по telegram_id (old device-based model)
                user = await self._user_gateway.get_by_user_id(pending.user_id)
                if user is None:
                    raise UserDeviceNotFound(pending.user_id)
                legacy_device = None
                if user.telegram_id is not None:
                    legacy_device = await self._gateway.get_active_by_telegram_id(user.telegram_id)
                if legacy_device is None or legacy_device.subscription is None:
                    raise SubscriptionNotFound(0)
                sub = legacy_device.subscription
                base = sub.end_date if sub.end_date > now else now
                sub.end_date = base + relativedelta(months=pending.duration)
                sub.plan = pending.duration
                legacy_device.device_limit = pending.device_limit
                await self._gateway.save(legacy_device)
                end_date = sub.end_date
                user_sub = UserSubscription(
                    user_id=pending.user_id,
                    plan=pending.duration,
                    start_date=now,
                    end_date=end_date,
                    device_limit=pending.device_limit,
                )
                user_sub = await self._subscription_gateway.save(user_sub)
        else:
            raise ValueError(f"Unknown pending action: {pending.action}")

        # Считаем платные платежи до текущего (для определения первой оплаты)
        existing_paid_count = await self._subscription_gateway.count_payments_for_user(
            pending.user_id
        )

        # Сохраняем Payment
        payment = UserPayment(
            user_id=pending.user_id,
            subscription_id=user_sub.id,
            amount=pending.amount,
            duration=pending.duration,
            device_limit=pending.device_limit,
        )
        await self._subscription_gateway.save_payment(payment)

        # Получаем User + обрабатываем баланс и Remnawave
        user = await self._user_gateway.get_by_user_id(pending.user_id)
        if user is None:
            raise UserDeviceNotFound(pending.user_id)

        if pending.balance_to_deduct > 0:
            if user.balance < pending.balance_to_deduct:
                raise InsufficientBalance(
                    pending.user_id, user.balance, pending.balance_to_deduct
                )
            user.balance -= pending.balance_to_deduct

        if user.remnawave_uuid is None:
            rw_info = await self._remnawave_gateway.create_user(
                user_id=pending.user_id,
                telegram_id=user.telegram_id,
                expire_at=end_date,
                device_limit=pending.device_limit,
            )
            user.remnawave_uuid = rw_info.uuid
            user.subscription_url = rw_info.subscription_url
        else:
            try:
                await self._remnawave_gateway.update_user(
                    uuid=user.remnawave_uuid,
                    expire_at=end_date,
                    device_limit=pending.device_limit,
                )
            except RemnawaveUserNotFound:
                # UUID устарел — ищем по telegram_id если есть, иначе создаём заново
                existing = None
                if user.telegram_id is not None:
                    existing = await self._remnawave_gateway.get_user_by_telegram_id(
                        user.telegram_id
                    )
                if existing is not None:
                    user.remnawave_uuid = existing.uuid
                    user.subscription_url = existing.subscription_url
                    await self._remnawave_gateway.update_user(
                        uuid=existing.uuid,
                        expire_at=end_date,
                        device_limit=pending.device_limit,
                    )
                else:
                    rw_info = await self._remnawave_gateway.create_user(
                        user_id=pending.user_id,
                        telegram_id=user.telegram_id,
                        expire_at=end_date,
                        device_limit=pending.device_limit,
                    )
                    user.remnawave_uuid = rw_info.uuid
                    user.subscription_url = rw_info.subscription_url
            if user.subscription_url is None:
                raise ValueError(f"User {pending.user_id} has remnawave_uuid but no subscription_url")

        # Реферальный бонус — только при первой платной покупке
        referrer_telegram_id: int | None = None
        if existing_paid_count == 0 and user.referred_by is not None:
            referrer = await self._user_gateway.get_by_telegram_id(user.referred_by)
            if referrer is not None:
                referrer.balance += 50
                await self._user_gateway.save(referrer)
                referrer_telegram_id = referrer.telegram_id

        await self._user_gateway.save(user)
        await self._pending_gateway.delete(cmd.pending_id)
        await self._uow.commit()

        return ConfirmPaymentResult(
            user_telegram_id=user.telegram_id,  # None for web-only — webhook handles gracefully
            device_name="vpn",
            action=pending.action,
            subscription_url=user.subscription_url,
            end_date=end_date,
            amount=pending.amount,
            duration=pending.duration,
            device_limit=pending.device_limit,
            referrer_telegram_id=referrer_telegram_id,
        )
```

- [ ] **Step 5: Update reject_payment**

Replace `reject_payment` method body:

```python
    async def reject_payment(self, cmd: RejectPayment) -> PendingPaymentInfo:
        pending = await self._pending_gateway.get_by_id(cmd.pending_id)
        if pending is None:
            raise PendingPaymentNotFound(cmd.pending_id)
        info = PendingPaymentInfo(
            id=pending.id,  # type: ignore[arg-type]
            user_id=pending.user_id,
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

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/application/interactor.py
git commit -m "refactor: DeviceInteractor uses user_id, fixes Remnawave recovery for web-only"
```

---

### Task 9: Update Tests for DeviceInteractor

**Files:**
- Modify: `tests/unit/device/test_device_interactor.py`
- Modify: `tests/unit/device/test_subscription_gateway.py`

- [ ] **Step 1: Fix helpers in test_device_interactor.py**

Find all `_make_user_subscription`, `_make_pending_payment` helper functions, and update them:

```python
def _make_user(telegram_id: int = 111, user_id_override: int | None = None) -> User:
    u = User(telegram_id=telegram_id, balance=0)
    # user_id is set by DB, simulate it via a simple approach in tests
    return u


def _make_pending(
    user_id: int = 42,
    action: str = "new",
    duration: int = 1,
    amount: int = 150,
    balance_to_deduct: int = 0,
    device_limit: int = 1,
) -> PendingPayment:
    return PendingPayment(
        id=1,
        user_id=user_id,
        action=action,
        device_type="vpn",
        duration=duration,
        amount=amount,
        balance_to_deduct=balance_to_deduct,
        device_limit=device_limit,
        created_at=datetime.now(UTC),
    )


def _make_user_subscription(
    user_id: int = 42,
    end_date: datetime | None = None,
) -> UserSubscription:
    now = datetime.now(UTC)
    return UserSubscription(
        id=1,
        user_id=user_id,
        plan=1,
        start_date=now,
        end_date=end_date or (now + timedelta(days=30)),
        device_limit=1,
    )
```

- [ ] **Step 2: Update all test cases that use old field names**

Search for `user_telegram_id` in the test file and replace with `user_id`:

```bash
grep -n "user_telegram_id" tests/unit/device/test_device_interactor.py
```

For each occurrence, update the mock setup and assertions to use `user_id`.

Key pattern to find and fix — mock return for `pending_gateway.get_by_id`:
```python
# Before
mock_pending_gateway.get_by_id.return_value = PendingPayment(
    id=1, user_telegram_id=111, action="new", ...
)
# After
mock_pending_gateway.get_by_id.return_value = _make_pending(user_id=42, action="new", ...)
```

And assertions on result:
```python
# Before
assert result.user_telegram_id == 111
# After
assert result.user_telegram_id == 111  # still in ConfirmPaymentResult (telegram_id from user)
```

Note: `ConfirmPaymentResult.user_telegram_id` remains but now comes from `user.telegram_id`, not pending.

Mock `user_gateway.get_by_user_id` instead of `get_by_telegram_id` for pending lookups:
```python
mock_user_gateway.get_by_user_id = AsyncMock(return_value=_make_user(telegram_id=111))
```

- [ ] **Step 3: Run tests and verify all pass**

```bash
uv run pytest tests/unit/device/test_device_interactor.py -v
```

Expected: all PASS

- [ ] **Step 4: Fix test_subscription_gateway.py**

```bash
grep -n "user_telegram_id" tests/unit/device/test_subscription_gateway.py
```

Update any occurrences — replace `user_telegram_id=X` with `user_id=X` in `UserSubscription` and `UserPayment` instantiations.

- [ ] **Step 5: Run all unit tests**

```bash
uv run pytest tests/unit/ -v
```

Expected: all PASS (or identify any remaining failures and fix them)

- [ ] **Step 6: Commit**

```bash
git add tests/unit/device/test_device_interactor.py tests/unit/device/test_subscription_gateway.py
git commit -m "test: update interactor and subscription gateway tests for user_id"
```

---

### Task 10: Update Bot Controllers

**Files:**
- Modify: `src/apps/device/controllers/bot/router.py`

- [ ] **Step 1: Update _show_payment_link helper and handle_vpn_flow**

In `src/apps/device/controllers/bot/router.py`, update `_show_payment_link` signature:

```python
async def _show_payment_link(
    msg_or_call: types.Message | types.CallbackQuery,
    interactor: DeviceInteractor,
    action: str,
    device: str,
    device_limit: int,
    duration: int,
    amount: int,
    balance: int,
    device_name: str | None,
    user_id: int,             # was user_telegram_id: int
) -> None:
    """Создать pending, получить ссылку ЮKassa и отправить пользователю."""
    pending = await interactor.create_pending_payment(
        CreatePendingPayment(
            user_id=user_id,   # was user_telegram_id
            action=action,
            device_type=device,
            duration=duration,
            amount=amount,
            balance_to_deduct=balance,
            device_limit=device_limit,
            device_name=device_name,
        )
    )
    ...  # rest stays the same
```

In `handle_vpn_flow`, at the start of the function (after the existing variable assignments), add user_id resolution:

```python
@router.callback_query(VpnCallback.filter())
async def handle_vpn_flow(
    call: types.CallbackQuery,
    callback_data: VpnCallback,
    bot: Bot,
    interactor: FromDishka[DeviceInteractor],
    user_interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
) -> None:
    action = callback_data.action
    device_limit = callback_data.device_limit
    duration = callback_data.duration
    referral_id = callback_data.referral_id
    payment = callback_data.payment
    balance = callback_data.balance
    choice = callback_data.choice

    # Resolve telegram_id → internal user_id for all interactor calls
    user_id = await user_view.get_user_id(call.from_user.id)
    if user_id is None:
        await call.answer("Ошибка: пользователь не найден")
        return

    # Реферальный бесплатный период
    if action == VpnAction.REFERRAL:
        ...
        result_free = await interactor.create_device_free(
            CreateDeviceFree(
                user_id=user_id,   # was telegram_id=call.from_user.id
                device_type="vpn",
                period_days=app_config.payment.free_month,
                device_limit=1,
            )
        )
        ...
```

Also update all calls to `_show_payment_link` within `handle_vpn_flow` — change `user_telegram_id=call.from_user.id` to `user_id=user_id`.

- [ ] **Step 2: Verify bot imports compile**

```bash
uv run python -c "from src.apps.device.controllers.bot.router import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/apps/device/controllers/bot/router.py
git commit -m "refactor: bot controller resolves telegram_id to user_id before interactor calls"
```

---

### Task 11: Update YooKassa Webhook — guard for web-only users

**Files:**
- Modify: `src/apps/device/controllers/http/yookassa_router.py`

- [ ] **Step 1: Guard bot notifications for web-only users**

In `yookassa_router.py`, update the notification section after `confirm_payment`:

```python
    # Уведомляем пользователя через бот (только если есть telegram_id)
    if result.user_telegram_id is not None:
        await _notify_user(bot, result)

    if result.referrer_telegram_id is not None:
        try:
            await bot.send_message(
                chat_id=result.referrer_telegram_id,
                text="🎉 Ваш друг оформил подписку! Вам начислено 50 руб. на баланс.",
            )
        except Exception:
            log.warning("referral_bonus_notify_failed", referrer_id=result.referrer_telegram_id)

    # Уведомляем админа
    end_str = result.end_date.strftime("%d.%m.%Y")
    action_label = "Новая подписка" if result.action == "new" else "Продление"
    details = (
        f"📱 Устройств: {result.device_limit} | 📅 {result.duration} мес | 💳 {result.amount}₽"
    )
    user_label = str(result.user_telegram_id) if result.user_telegram_id else f"web-user"
    await bot.send_message(
        chat_id=app_config.bot.admin_id,
        text=(
            f"✅ ЮKassa автоплатёж\n"
            f"👤 {user_label}\n"
            f"{action_label} до {end_str}\n"
            f"{details}\n"
            f"payment_id: {payment_id}"
        ),
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/apps/device/controllers/http/yookassa_router.py
git commit -m "fix: yookassa webhook guards bot notifications for web-only users"
```

---

### Task 12: Fix HTTP User Controller for web-only

**Files:**
- Modify: `src/apps/user/controllers/http/router.py`

- [ ] **Step 1: Fix get_me to return real data for web-only users**

Replace `get_me` endpoint in `src/apps/user/controllers/http/router.py`:

```python
@router.get("/me")
async def get_me(
    user_id: CurrentUser,
    user_view: FromDishka[UserView],
) -> dict:
    telegram_id = await user_view.get_telegram_id(user_id)
    balance = await user_view.get_balance_by_user_id(user_id)
    referral_code = await user_view.get_referral_code_by_user_id(user_id)
    return {
        "user_id": user_id,
        "telegram_id": telegram_id,
        "balance": balance,
        "referral_code": referral_code,
    }
```

This requires two new view methods. Add them to `UserView` interface and `SQLAlchemyUserView` adapter:

In `src/apps/user/application/interfaces/view.py`, add to `UserView`:

```python
    async def get_balance_by_user_id(self, user_id: int) -> int: ...

    async def get_referral_code_by_user_id(self, user_id: int) -> str | None: ...
```

In `src/apps/user/adapters/view.py`, add to `SQLAlchemyUserView`:

```python
    async def get_balance_by_user_id(self, user_id: int) -> int:
        result = await self._session.execute(
            select(UserORM.balance).where(UserORM.id == user_id)
        )
        return result.scalar_one_or_none() or 0

    async def get_referral_code_by_user_id(self, user_id: int) -> str | None:
        result = await self._session.execute(
            select(UserORM.referral_code).where(UserORM.id == user_id)
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 2: Fix Auth interactor — remove inline ORM import**

In `src/apps/auth/application/interactor.py`, replace the messy inline query at lines 79–88 with the proper view call. Change `verify_otp` end:

```python
        await self._uow.commit()

        # Получаем user_id через view (без прямого ORM доступа)
        db_user_id = await self._user_view.get_user_id_by_email(cmd.email)
        assert db_user_id is not None

        token = create_jwt(db_user_id)
        return AuthResult(access_token=token, user_id=db_user_id)
```

This requires adding `get_user_id_by_email` to `UserView`:

In `src/apps/user/application/interfaces/view.py`:
```python
    async def get_user_id_by_email(self, email: str) -> int | None: ...
```

In `src/apps/user/adapters/view.py`:
```python
    async def get_user_id_by_email(self, email: str) -> int | None:
        result = await self._session.execute(
            select(UserORM.id).where(UserORM.email == email)
        )
        return result.scalar_one_or_none()
```

And inject `UserView` into `AuthInteractor` (add to `__init__` and DI provider in `src/apps/auth/ioc.py`).

- [ ] **Step 3: Run all unit tests**

```bash
uv run pytest tests/unit/ -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add src/apps/user/controllers/http/router.py \
        src/apps/user/application/interfaces/view.py \
        src/apps/user/adapters/view.py \
        src/apps/auth/application/interactor.py \
        src/apps/auth/ioc.py
git commit -m "fix: get_me returns real data for web-only users, clean up auth interactor"
```

---

### Task 13: Final verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/unit/ -v --tb=short
```

Expected: all PASS

- [ ] **Step 2: Grep for remaining user_telegram_id in domain/application code**

```bash
grep -rn "user_telegram_id" src/apps/device/domain/ src/apps/device/application/
```

Expected: zero matches (confirms refactoring is complete)

- [ ] **Step 3: Check types**

```bash
uv run ruff check --fix && uv run ruff format
```

Expected: no errors

- [ ] **Step 4: Final commit tag**

```bash
git tag foundation-user-id-complete
```
