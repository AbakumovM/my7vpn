# Referral Anti-Fraud & Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix broken referral flow, prevent fraud (self-referral, existing users, fake accounts), defer bonus to first paid purchase.

**Architecture:** Domain primitives first (exceptions, protocol methods), then interactor logic (free subscription via UserSubscription, deferred bonus), then controllers (validation guards, simplified REFERRAL path, referrer notifications in both bot and HTTP controllers).

**Tech Stack:** Python 3.12, Aiogram 3, SQLAlchemy 2 async, Dishka, pytest + pytest-asyncio, AsyncMock

---

### Task 1: Domain primitives — SelfReferralError, CreateDeviceFree.device_limit, count_payments_for_user protocol

**Files:**
- Modify: `src/apps/user/domain/exceptions.py`
- Modify: `src/apps/device/domain/commands.py`
- Modify: `src/apps/device/application/interfaces/subscription_gateway.py`

- [ ] **Step 1: Add `SelfReferralError` to exceptions**

`src/apps/user/domain/exceptions.py`:
```python
class UserNotFound(Exception):
    def __init__(self, telegram_id: int) -> None:
        super().__init__(f"User {telegram_id} not found")
        self.telegram_id = telegram_id


class ReferralNotFound(Exception):
    def __init__(self, referral_code: str) -> None:
        super().__init__(f"Referral code '{referral_code}' not found")
        self.referral_code = referral_code


class SelfReferralError(Exception):
    def __init__(self, telegram_id: int) -> None:
        super().__init__(f"User {telegram_id} cannot use their own referral code")
        self.telegram_id = telegram_id


class InsufficientBalance(Exception):
    def __init__(self, telegram_id: int, balance: int, required: int) -> None:
        super().__init__(f"User {telegram_id} has {balance}, required {required}")
        self.telegram_id = telegram_id
        self.balance = balance
        self.required = required
```

- [ ] **Step 2: Add `device_limit` field to `CreateDeviceFree`**

`src/apps/device/domain/commands.py` — update the `CreateDeviceFree` dataclass:
```python
@dataclass(frozen=True)
class CreateDeviceFree:
    telegram_id: int
    device_type: str
    period_days: int
    device_limit: int = 1
```

- [ ] **Step 3: Add `count_payments_for_user` to `SubscriptionGateway` protocol**

`src/apps/device/application/interfaces/subscription_gateway.py`:
```python
from typing import Protocol

from src.apps.device.domain.models import UserPayment, UserSubscription


class SubscriptionGateway(Protocol):
    async def get_active_by_telegram_id(self, telegram_id: int) -> UserSubscription | None: ...

    async def save(self, sub: UserSubscription) -> UserSubscription: ...

    async def save_payment(self, payment: UserPayment) -> UserPayment: ...

    async def count_payments_for_user(self, telegram_id: int) -> int:
        """Count paid (amount > 0) UserPayment records for the user."""
        ...
```

- [ ] **Step 4: Commit**

```bash
git add src/apps/user/domain/exceptions.py src/apps/device/domain/commands.py src/apps/device/application/interfaces/subscription_gateway.py
git commit -m "feat: add SelfReferralError, device_limit to CreateDeviceFree, count_payments_for_user protocol"
```

---

### Task 2: count_payments_for_user adapter implementation

**Files:**
- Modify: `src/apps/device/adapters/gateway.py`
- Test: `tests/unit/device/test_device_interactor.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/device/test_device_interactor.py`:
```python
from src.apps.device.adapters.gateway import SQLAlchemySubscriptionGateway
```

Create `tests/unit/device/test_subscription_gateway.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.gateway import SQLAlchemySubscriptionGateway


pytestmark = pytest.mark.asyncio


class TestCountPaymentsForUser:
    async def test_returns_count_of_paid_payments(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 3
        session.execute.return_value = mock_result

        gw = SQLAlchemySubscriptionGateway(session)
        count = await gw.count_payments_for_user(telegram_id=111)

        assert count == 3
        session.execute.assert_awaited_once()

    async def test_returns_zero_when_no_paid_payments(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        session.execute.return_value = mock_result

        gw = SQLAlchemySubscriptionGateway(session)
        count = await gw.count_payments_for_user(telegram_id=999)

        assert count == 0
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/unit/device/test_subscription_gateway.py -v
```
Expected: `FAILED` — `SQLAlchemySubscriptionGateway` has no `count_payments_for_user`.

- [ ] **Step 3: Implement `count_payments_for_user` in `SQLAlchemySubscriptionGateway`**

Add to `SQLAlchemySubscriptionGateway` in `src/apps/device/adapters/gateway.py`:
```python
async def count_payments_for_user(self, telegram_id: int) -> int:
    result = await self._session.execute(
        select(func.count(UserPaymentORM.id))
        .where(UserPaymentORM.user_telegram_id == telegram_id)
        .where(UserPaymentORM.amount > 0)
    )
    return result.scalar_one()
```

Make sure `func` is imported: `from sqlalchemy import func, select` (already imported at the top of the file).

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run pytest tests/unit/device/test_subscription_gateway.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/apps/device/adapters/gateway.py tests/unit/device/test_subscription_gateway.py
git commit -m "feat: implement count_payments_for_user in SQLAlchemySubscriptionGateway"
```

---

### Task 3: UserView — get_referrer_telegram_id

**Files:**
- Modify: `src/apps/user/application/interfaces/view.py`
- Modify: `src/apps/user/adapters/view.py`

- [ ] **Step 1: Add method to `UserView` protocol**

`src/apps/user/application/interfaces/view.py`:
```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ReferralStats:
    invited_count: int
    total_earned: int
    balance: int


class UserView(Protocol):
    async def get_balance(self, telegram_id: int) -> int: ...

    async def get_referral_code(self, telegram_id: int) -> str | None: ...

    async def get_device_count(self, telegram_id: int) -> int: ...

    async def get_email(self, telegram_id: int) -> str | None: ...

    async def get_user_id(self, telegram_id: int) -> int | None: ...

    async def get_telegram_id(self, user_id: int) -> int | None: ...

    async def get_referral_stats(self, telegram_id: int) -> ReferralStats: ...

    async def get_remnawave_uuid(self, telegram_id: int) -> str | None: ...

    async def get_referrer_telegram_id(self, referral_code: str) -> int | None:
        """Return telegram_id of the user who owns this referral code, or None."""
        ...
```

- [ ] **Step 2: Implement in `SQLAlchemyUserView`**

Add to `SQLAlchemyUserView` in `src/apps/user/adapters/view.py`:
```python
async def get_referrer_telegram_id(self, referral_code: str) -> int | None:
    result = await self._session.execute(
        select(UserORM.telegram_id).where(UserORM.referral_code == referral_code)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 3: Run existing tests to verify no regressions**

```bash
uv run pytest tests/unit/user/ -v
```
Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/apps/user/application/interfaces/view.py src/apps/user/adapters/view.py
git commit -m "feat: add get_referrer_telegram_id to UserView"
```

---

### Task 4: create_device_free refactor — UserSubscription + Remnawave

**Files:**
- Modify: `src/apps/device/application/interactor.py`
- Test: `tests/unit/device/test_device_interactor.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/device/test_device_interactor.py`:
```python
from src.apps.device.application.interactor import FreeSubscriptionInfo
from src.apps.device.domain.commands import CreateDeviceFree
```

Add test class after existing tests:
```python
class TestCreateDeviceFree:
    async def test_creates_user_subscription_and_remnawave_new_user(
        self,
        interactor: DeviceInteractor,
        mock_user_gateway: AsyncMock,
        mock_remnawave_gateway: AsyncMock,
        mock_subscription_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ) -> None:
        user = User(telegram_id=42, balance=0, remnawave_uuid=None)
        mock_user_gateway.get_by_telegram_id.return_value = user

        rw_info = RemnawaveUserInfo(
            uuid="rw-uuid-123",
            username="user42",
            subscription_url="https://sub.example.com/42",
            expire_at=datetime.now(UTC) + timedelta(days=5),
            status="ACTIVE",
            hwid_device_limit=1,
            telegram_id=42,
        )
        mock_remnawave_gateway.create_user.return_value = rw_info

        saved_sub = UserSubscription(
            id=77,
            user_telegram_id=42,
            plan=5,
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC) + timedelta(days=5),
            device_limit=1,
        )
        mock_subscription_gateway.save.return_value = saved_sub

        from src.apps.device.domain.models import UserPayment
        saved_payment = UserPayment(
            id=1, user_telegram_id=42, amount=0, duration=5, device_limit=1
        )
        mock_subscription_gateway.save_payment.return_value = saved_payment

        cmd = CreateDeviceFree(telegram_id=42, device_type="vpn", period_days=5, device_limit=1)
        result = await interactor.create_device_free(cmd)

        assert isinstance(result, FreeSubscriptionInfo)
        assert result.user_telegram_id == 42
        assert result.subscription_url == "https://sub.example.com/42"
        mock_remnawave_gateway.create_user.assert_awaited_once()
        mock_subscription_gateway.save.assert_awaited_once()
        mock_subscription_gateway.save_payment.assert_awaited_once()
        mock_uow.commit.assert_awaited_once()

    async def test_uses_update_user_when_remnawave_uuid_exists(
        self,
        interactor: DeviceInteractor,
        mock_user_gateway: AsyncMock,
        mock_remnawave_gateway: AsyncMock,
        mock_subscription_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ) -> None:
        user = User(
            telegram_id=42,
            balance=0,
            remnawave_uuid="existing-uuid",
            subscription_url="https://sub.example.com/42",
        )
        mock_user_gateway.get_by_telegram_id.return_value = user

        mock_remnawave_gateway.update_user.return_value = RemnawaveUserInfo(
            uuid="existing-uuid",
            username="user42",
            subscription_url="https://sub.example.com/42",
            expire_at=datetime.now(UTC) + timedelta(days=5),
            status="ACTIVE",
            hwid_device_limit=1,
            telegram_id=42,
        )

        saved_sub = UserSubscription(
            id=77,
            user_telegram_id=42,
            plan=5,
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC) + timedelta(days=5),
            device_limit=1,
        )
        mock_subscription_gateway.save.return_value = saved_sub

        from src.apps.device.domain.models import UserPayment
        mock_subscription_gateway.save_payment.return_value = UserPayment(
            id=2, user_telegram_id=42, amount=0, duration=5, device_limit=1
        )

        cmd = CreateDeviceFree(telegram_id=42, device_type="vpn", period_days=5, device_limit=1)
        result = await interactor.create_device_free(cmd)

        mock_remnawave_gateway.create_user.assert_not_awaited()
        mock_remnawave_gateway.update_user.assert_awaited_once()
        assert result.subscription_url == "https://sub.example.com/42"
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/unit/device/test_device_interactor.py::TestCreateDeviceFree -v
```
Expected: `FAILED` — `FreeSubscriptionInfo` not defined, old implementation returns `DeviceCreatedInfo`.

- [ ] **Step 3: Add `FreeSubscriptionInfo` and rewrite `create_device_free`**

In `src/apps/device/application/interactor.py`, add after existing dataclasses (around line 64):
```python
@dataclass(frozen=True)
class FreeSubscriptionInfo:
    user_telegram_id: int
    subscription_url: str
    end_date: datetime
```

Replace the `create_device_free` method entirely:
```python
async def create_device_free(self, cmd: CreateDeviceFree) -> FreeSubscriptionInfo:
    user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
    if user is None:
        raise UserDeviceNotFound(cmd.telegram_id)

    now = datetime.now(UTC)
    end_date = now + relativedelta(days=cmd.period_days)

    if user.remnawave_uuid is None:
        rw_info = await self._remnawave_gateway.create_user(
            telegram_id=cmd.telegram_id,
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
            raise ValueError(
                f"User {cmd.telegram_id} has remnawave_uuid but no subscription_url"
            )

    await self._user_gateway.save(user)

    user_sub = UserSubscription(
        user_telegram_id=cmd.telegram_id,
        plan=cmd.period_days,
        start_date=now,
        end_date=end_date,
        device_limit=cmd.device_limit,
    )
    user_sub = await self._subscription_gateway.save(user_sub)

    payment = UserPayment(
        user_telegram_id=cmd.telegram_id,
        subscription_id=user_sub.id,
        amount=0,
        duration=cmd.period_days,
        device_limit=cmd.device_limit,
        payment_method="реферал",
    )
    await self._subscription_gateway.save_payment(payment)
    await self._uow.commit()

    return FreeSubscriptionInfo(
        user_telegram_id=cmd.telegram_id,
        subscription_url=user.subscription_url,  # type: ignore[arg-type]  # set above or existed
        end_date=end_date,
    )
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run pytest tests/unit/device/test_device_interactor.py::TestCreateDeviceFree -v
```
Expected: 2 tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
uv run pytest tests/unit/ -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/application/interactor.py tests/unit/device/test_device_interactor.py
git commit -m "feat: create_device_free now creates UserSubscription via Remnawave"
```

---

### Task 5: confirm_payment — deferred referral bonus

**Files:**
- Modify: `src/apps/device/application/interactor.py`
- Test: `tests/unit/device/test_device_interactor.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/device/test_device_interactor.py` inside `TestConfirmPayment` class (or add a new class):
```python
class TestConfirmPaymentReferralBonus:
    def _make_pending(
        self,
        pending_id: int = 1,
        user_telegram_id: int = 42,
        action: str = "new",
        duration: int = 1,
        amount: int = 150,
        device_limit: int = 1,
        balance_to_deduct: int = 0,
    ) -> PendingPayment:
        return PendingPayment(
            id=pending_id,
            user_telegram_id=user_telegram_id,
            action=action,
            device_type="vpn",
            duration=duration,
            amount=amount,
            balance_to_deduct=balance_to_deduct,
            device_limit=device_limit,
            created_at=datetime.now(UTC),
        )

    async def test_bonus_credited_on_first_paid_payment(
        self,
        interactor: DeviceInteractor,
        mock_pending_gateway: AsyncMock,
        mock_subscription_gateway: AsyncMock,
        mock_user_gateway: AsyncMock,
        mock_remnawave_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ) -> None:
        pending = self._make_pending()
        mock_pending_gateway.get_by_id.return_value = pending

        user = User(telegram_id=42, balance=0, referred_by=99, remnawave_uuid="rw-uuid")
        user.subscription_url = "https://sub.example.com"
        referrer = User(telegram_id=99, balance=100)
        mock_user_gateway.get_by_telegram_id.side_effect = lambda tid: (
            user if tid == 42 else referrer
        )

        saved_sub = _make_user_subscription(telegram_id=42, sub_id=10)
        mock_subscription_gateway.get_active_by_telegram_id.return_value = None
        mock_subscription_gateway.save.return_value = saved_sub
        mock_subscription_gateway.count_payments_for_user.return_value = 0

        from src.apps.device.domain.models import UserPayment
        mock_subscription_gateway.save_payment.return_value = UserPayment(
            id=5, user_telegram_id=42, amount=150, duration=1, device_limit=1
        )
        mock_remnawave_gateway.create_user.return_value = RemnawaveUserInfo(
            uuid="rw-uuid", username="u42", subscription_url="https://sub.example.com",
            expire_at=datetime.now(UTC) + timedelta(days=30),
            status="ACTIVE", hwid_device_limit=1, telegram_id=42,
        )

        result = await interactor.confirm_payment(ConfirmPayment(pending_id=1))

        assert result.referrer_telegram_id == 99
        # referrer balance increased by 50
        save_calls = mock_user_gateway.save.await_args_list
        saved_users = [call.args[0] for call in save_calls]
        referrer_saves = [u for u in saved_users if u.telegram_id == 99]
        assert len(referrer_saves) == 1
        assert referrer_saves[0].balance == 150  # 100 + 50

    async def test_no_bonus_on_second_payment(
        self,
        interactor: DeviceInteractor,
        mock_pending_gateway: AsyncMock,
        mock_subscription_gateway: AsyncMock,
        mock_user_gateway: AsyncMock,
        mock_remnawave_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ) -> None:
        pending = self._make_pending()
        mock_pending_gateway.get_by_id.return_value = pending

        user = User(telegram_id=42, balance=0, referred_by=99, remnawave_uuid="rw-uuid")
        user.subscription_url = "https://sub.example.com"
        mock_user_gateway.get_by_telegram_id.return_value = user

        saved_sub = _make_user_subscription(telegram_id=42, sub_id=10)
        mock_subscription_gateway.get_active_by_telegram_id.return_value = None
        mock_subscription_gateway.save.return_value = saved_sub
        mock_subscription_gateway.count_payments_for_user.return_value = 1  # already has a payment

        from src.apps.device.domain.models import UserPayment
        mock_subscription_gateway.save_payment.return_value = UserPayment(
            id=5, user_telegram_id=42, amount=150, duration=1, device_limit=1
        )
        mock_remnawave_gateway.create_user.return_value = RemnawaveUserInfo(
            uuid="rw-uuid", username="u42", subscription_url="https://sub.example.com",
            expire_at=datetime.now(UTC) + timedelta(days=30),
            status="ACTIVE", hwid_device_limit=1, telegram_id=42,
        )

        result = await interactor.confirm_payment(ConfirmPayment(pending_id=1))

        assert result.referrer_telegram_id is None

    async def test_no_bonus_without_referrer(
        self,
        interactor: DeviceInteractor,
        mock_pending_gateway: AsyncMock,
        mock_subscription_gateway: AsyncMock,
        mock_user_gateway: AsyncMock,
        mock_remnawave_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ) -> None:
        pending = self._make_pending()
        mock_pending_gateway.get_by_id.return_value = pending

        user = User(telegram_id=42, balance=0, referred_by=None, remnawave_uuid="rw-uuid")
        user.subscription_url = "https://sub.example.com"
        mock_user_gateway.get_by_telegram_id.return_value = user

        saved_sub = _make_user_subscription(telegram_id=42, sub_id=10)
        mock_subscription_gateway.get_active_by_telegram_id.return_value = None
        mock_subscription_gateway.save.return_value = saved_sub
        mock_subscription_gateway.count_payments_for_user.return_value = 0

        from src.apps.device.domain.models import UserPayment
        mock_subscription_gateway.save_payment.return_value = UserPayment(
            id=5, user_telegram_id=42, amount=150, duration=1, device_limit=1
        )
        mock_remnawave_gateway.create_user.return_value = RemnawaveUserInfo(
            uuid="rw-uuid", username="u42", subscription_url="https://sub.example.com",
            expire_at=datetime.now(UTC) + timedelta(days=30),
            status="ACTIVE", hwid_device_limit=1, telegram_id=42,
        )

        result = await interactor.confirm_payment(ConfirmPayment(pending_id=1))

        assert result.referrer_telegram_id is None

    async def test_no_bonus_when_referrer_not_found(
        self,
        interactor: DeviceInteractor,
        mock_pending_gateway: AsyncMock,
        mock_subscription_gateway: AsyncMock,
        mock_user_gateway: AsyncMock,
        mock_remnawave_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ) -> None:
        pending = self._make_pending()
        mock_pending_gateway.get_by_id.return_value = pending

        user = User(telegram_id=42, balance=0, referred_by=99, remnawave_uuid="rw-uuid")
        user.subscription_url = "https://sub.example.com"

        def get_user(tid: int) -> User | None:
            if tid == 42:
                return user
            return None  # referrer not found

        mock_user_gateway.get_by_telegram_id.side_effect = get_user

        saved_sub = _make_user_subscription(telegram_id=42, sub_id=10)
        mock_subscription_gateway.get_active_by_telegram_id.return_value = None
        mock_subscription_gateway.save.return_value = saved_sub
        mock_subscription_gateway.count_payments_for_user.return_value = 0

        from src.apps.device.domain.models import UserPayment
        mock_subscription_gateway.save_payment.return_value = UserPayment(
            id=5, user_telegram_id=42, amount=150, duration=1, device_limit=1
        )
        mock_remnawave_gateway.create_user.return_value = RemnawaveUserInfo(
            uuid="rw-uuid", username="u42", subscription_url="https://sub.example.com",
            expire_at=datetime.now(UTC) + timedelta(days=30),
            status="ACTIVE", hwid_device_limit=1, telegram_id=42,
        )

        result = await interactor.confirm_payment(ConfirmPayment(pending_id=1))

        assert result.referrer_telegram_id is None
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/unit/device/test_device_interactor.py::TestConfirmPaymentReferralBonus -v
```
Expected: `FAILED` — `ConfirmPaymentResult` has no `referrer_telegram_id`, `count_payments_for_user` not called.

- [ ] **Step 3: Update `ConfirmPaymentResult` and `confirm_payment`**

In `src/apps/device/application/interactor.py`:

Update `ConfirmPaymentResult`:
```python
@dataclass(frozen=True)
class ConfirmPaymentResult:
    user_telegram_id: int
    device_name: str
    action: str              # "new" | "renew"
    subscription_url: str | None
    end_date: datetime
    referrer_telegram_id: int | None = None
```

In the `confirm_payment` method, replace the section starting with `# Сохраняем Payment` through the `return` statement:

```python
        # Считаем платные платежи до текущего (для определения первой оплаты)
        existing_paid_count = await self._subscription_gateway.count_payments_for_user(
            pending.user_telegram_id
        )

        # Сохраняем Payment
        payment = UserPayment(
            user_telegram_id=pending.user_telegram_id,
            subscription_id=user_sub.id,
            amount=pending.amount,
            duration=pending.duration,
            device_limit=pending.device_limit,
        )
        await self._subscription_gateway.save_payment(payment)

        # Получаем User + обрабатываем баланс и Remnawave
        user = await self._user_gateway.get_by_telegram_id(pending.user_telegram_id)
        if user is None:
            raise UserDeviceNotFound(pending.user_telegram_id)

        if pending.balance_to_deduct > 0:
            if user.balance < pending.balance_to_deduct:
                raise InsufficientBalance(
                    pending.user_telegram_id, user.balance, pending.balance_to_deduct
                )
            user.balance -= pending.balance_to_deduct

        if user.remnawave_uuid is None:
            rw_info = await self._remnawave_gateway.create_user(
                telegram_id=pending.user_telegram_id,
                expire_at=end_date,
                device_limit=pending.device_limit,
            )
            user.remnawave_uuid = rw_info.uuid
            user.subscription_url = rw_info.subscription_url
        else:
            await self._remnawave_gateway.update_user(
                uuid=user.remnawave_uuid,
                expire_at=end_date,
                device_limit=pending.device_limit,
            )
            if user.subscription_url is None:
                raise ValueError(
                    f"User {pending.user_telegram_id} has remnawave_uuid but no subscription_url"
                )

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
            user_telegram_id=pending.user_telegram_id,
            device_name="vpn",
            action=pending.action,
            subscription_url=user.subscription_url,
            end_date=end_date,
            referrer_telegram_id=referrer_telegram_id,
        )
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run pytest tests/unit/device/test_device_interactor.py::TestConfirmPaymentReferralBonus -v
```
Expected: 4 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/unit/ -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/application/interactor.py tests/unit/device/test_device_interactor.py
git commit -m "feat: deferred referral bonus on first paid payment in confirm_payment"
```

---

### Task 6: handle_start validation guards

**Files:**
- Modify: `src/apps/user/controllers/bot/router.py`

- [ ] **Step 1: Add new keyboard function for referral activation**

In `src/common/bot/keyboards/keyboards.py`, add after `get_keyboard_friends`:
```python
def get_keyboard_referral_activate(referral_id: int) -> InlineKeyboardMarkup:
    """Экран реферальной активации — одна кнопка."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎁 Активировать бесплатный период",
                callback_data=VpnCallback(
                    action=VpnAction.REFERRAL,
                    referral_id=referral_id,
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data=CallbackAction.START,
            )
        ],
    ])
```

- [ ] **Step 2: Update `handle_start` in user bot router**

Replace the entire `if referral_code:` block in `handle_start` (`src/apps/user/controllers/bot/router.py`):

```python
@router.message(Command(CallbackAction.START))
async def handle_start(
    msg: types.Message,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
    device_view: FromDishka[DeviceView],
    remnawave_gateway: FromDishka[RemnawaveGateway],
) -> None:
    referral_code = msg.text.split(" ")[1] if len(msg.text.split(" ")) > 1 else None

    if referral_code:
        # 1. Код существует → получаем telegram_id реферера
        referral_id = await user_view.get_referrer_telegram_id(referral_code)
        if referral_id is None:
            await msg.answer(bot_repl.get_message_error_referral(), reply_markup=return_start())
            return

        # 2. Нельзя использовать свою ссылку
        if referral_id == msg.from_user.id:
            await msg.answer(
                "❌ Нельзя использовать собственную реферальную ссылку.",
                reply_markup=return_start(),
            )
            return

        # 3. Только новые пользователи
        existing_user_id = await user_view.get_user_id(msg.from_user.id)
        if existing_user_id is not None:
            await msg.answer(
                "Вы уже зарегистрированы. Используйте /start для входа в меню.",
                reply_markup=return_start(),
            )
            return

        # Создаём пользователя с привязкой к рефереру
        await interactor.get_or_create(
            GetOrCreateUser(telegram_id=msg.from_user.id, referred_by_code=referral_code)
        )

        await msg.answer(
            bot_repl.get_start_message_free_month(msg.from_user.full_name),
            reply_markup=get_keyboard_referral_activate(referral_id=referral_id),
        )
        return

    user = await interactor.get_or_create(GetOrCreateUser(telegram_id=msg.from_user.id))
    sub = await device_view.get_subscription_info(msg.from_user.id)

    if sub and sub.end_date:
        end_str = sub.end_date.strftime("%d.%m.%Y")
        remnawave_uuid = await user_view.get_remnawave_uuid(msg.from_user.id)
        used = await _get_hwid_used(remnawave_uuid, remnawave_gateway)
        await msg.answer(
            bot_repl.get_main_menu_active(
                msg.from_user.full_name, end_str, used, sub.device_limit, user.balance
            ),
            reply_markup=get_keyboard_main_menu(has_subscription=True),
        )
    else:
        await msg.answer(
            bot_repl.get_main_menu_new(msg.from_user.full_name),
            reply_markup=get_keyboard_main_menu(has_subscription=False),
        )
```

Also update the import at the top of `src/apps/user/controllers/bot/router.py` — remove the unused `GetOrCreateUser` with `referred_by_code` import (it's still used), and remove `ReferralNotFound` from the import if it's no longer used in this file. Keep `GetOrCreateUser` and `GetReferralCode`.

Remove the line:
```python
from src.apps.user.domain.exceptions import ReferralNotFound
```
(it was only used in the old referral code path).

Update keyboards import to add `get_keyboard_referral_activate`:
```python
from src.common.bot.keyboards.keyboards import (
    get_keyboard_confirm_delete_all,
    get_keyboard_device_count,
    get_keyboard_friends,
    get_keyboard_hwid_devices,
    get_keyboard_instruction_platforms,
    get_keyboard_main_menu,
    get_keyboard_referral_activate,
    get_keyboard_subscription,
    return_start,
)
```

- [ ] **Step 3: Run ruff to check for issues**

```bash
uv run ruff check --fix src/apps/user/controllers/bot/router.py src/common/bot/keyboards/keyboards.py
uv run ruff format src/apps/user/controllers/bot/router.py src/common/bot/keyboards/keyboards.py
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add src/apps/user/controllers/bot/router.py src/common/bot/keyboards/keyboards.py
git commit -m "feat: add referral validation guards in handle_start (self-referral, existing user)"
```

---

### Task 7: handle_vpn_flow REFERRAL path + referrer notify in both controllers

**Files:**
- Modify: `src/apps/device/controllers/bot/router.py`
- Modify: `src/apps/device/controllers/http/yookassa_router.py`

- [ ] **Step 1: Rewrite REFERRAL branch in `handle_vpn_flow`**

In `src/apps/device/controllers/bot/router.py`, in `handle_vpn_flow`, add an early REFERRAL check as the **first branch** (before step 1):

```python
@router.callback_query(VpnCallback.filter())
async def handle_vpn_flow(
    call: types.CallbackQuery,
    callback_data: VpnCallback,
    bot: Bot,
    state: FSMContext,
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
    payment_status = callback_data.payment_status

    # Реферальный бесплатный период — обрабатываем первым, минуя все платёжные шаги
    if action == VpnAction.REFERRAL:
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            await call.answer()
            return
        await call.answer()

        result_free = await interactor.create_device_free(
            CreateDeviceFree(
                telegram_id=call.from_user.id,
                device_type="vpn",
                period_days=app_config.payment.free_month,
                device_limit=1,
            )
        )
        await user_interactor.mark_free_month_used(MarkFreeMonthUsed(telegram_id=call.from_user.id))
        log.info(
            "device_created_free",
            device_type="vpn",
            referral_id=referral_id,
        )
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🎁 Реферальная подписка!\n"
                f"👤 @{call.from_user.username} (id: {call.from_user.id})\n"
                f"🆔 Пригласил: {referral_id}"
            ),
        )
        await call.message.answer(
            "✅ Бесплатный период активирован!\n\n"
            "Ваша ссылка для подключения — скопируйте и вставьте в приложение Happ:\n\n"
            f"<code>{result_free.subscription_url}</code>",
            reply_markup=get_keyboard_vpn_received(),
        )
        return

    # Шаг 1: выбор количества устройств
    # ... (остальной код без изменений)
```

- [ ] **Step 2: Add referrer notify in `handle_admin_confirm`**

In `src/apps/device/controllers/bot/router.py`, in `handle_admin_confirm`, after `await call.message.edit_text(f"✅ Выдано: {result.device_name}")`, add:

```python
    if result.referrer_telegram_id is not None:
        try:
            await bot.send_message(
                chat_id=result.referrer_telegram_id,
                text="🎉 Ваш друг оформил подписку! Вам начислено 50 руб. на баланс.",
            )
        except Exception:
            log.warning("referral_bonus_notify_failed", referrer_id=result.referrer_telegram_id)
```

- [ ] **Step 3: Add referrer notify in `yookassa_webhook`**

In `src/apps/device/controllers/http/yookassa_router.py`, after `await _notify_user(bot, result)`, add:

```python
    if result.referrer_telegram_id is not None:
        try:
            await bot.send_message(
                chat_id=result.referrer_telegram_id,
                text="🎉 Ваш друг оформил подписку! Вам начислено 50 руб. на баланс.",
            )
        except Exception:
            log.warning("referral_bonus_notify_failed", referrer_id=result.referrer_telegram_id)
```

- [ ] **Step 4: Run ruff**

```bash
uv run ruff check --fix src/apps/device/controllers/bot/router.py src/apps/device/controllers/http/yookassa_router.py
uv run ruff format src/apps/device/controllers/bot/router.py src/apps/device/controllers/http/yookassa_router.py
```
Expected: no errors.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/unit/ -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/controllers/bot/router.py src/apps/device/controllers/http/yookassa_router.py
git commit -m "feat: fix REFERRAL flow in handle_vpn_flow, add referrer notify on first payment"
```
