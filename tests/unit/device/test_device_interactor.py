from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.apps.device.application.interactor import DeviceInteractor
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveUserInfo
from src.apps.device.domain.commands import ConfirmPayment, CreateDevice, CreatePendingPayment, DeleteDevice, RenewSubscription
from src.apps.device.domain.exceptions import DeviceNotFound, PendingPaymentNotFound, SubscriptionNotFound, UserDeviceNotFound
from src.apps.device.domain.models import Device, PendingPayment, Subscription
from src.apps.user.domain.exceptions import InsufficientBalance
from src.apps.user.domain.models import User


pytestmark = pytest.mark.asyncio


def _make_user(telegram_id: int = 111) -> User:
    return User(telegram_id=telegram_id, balance=0)


def _make_device(
    device_id: int = 1,
    device_name: str = "Android 1000",
    end_date: datetime | None = None,
) -> Device:
    now = datetime.now(timezone.utc)
    sub = Subscription(
        id=1,
        device_id=device_id,
        plan=1,
        start_date=now,
        end_date=end_date or (now + timedelta(days=30)),
    )
    return Device(id=device_id, user_id=111, device_name=device_name, subscription=sub)


class TestCreateDevice:
    async def test_creates_device_and_commits(
        self,
        interactor: DeviceInteractor,
        mock_gateway: AsyncMock,
        mock_user_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ) -> None:
        mock_user_gateway.get_by_telegram_id.return_value = _make_user()
        mock_gateway.get_next_seq.return_value = 5

        result = await interactor.create_device(
            CreateDevice(telegram_id=111, device_type="Android", period_months=1, amount=150)
        )

        mock_gateway.save.assert_called_once()
        mock_uow.commit.assert_called_once()
        assert "Android" in result.device_name
        assert result.user_telegram_id == 111

    async def test_raises_if_user_not_found(
        self,
        interactor: DeviceInteractor,
        mock_user_gateway: AsyncMock,
    ) -> None:
        mock_user_gateway.get_by_telegram_id.return_value = None

        with pytest.raises(UserDeviceNotFound):
            await interactor.create_device(
                CreateDevice(telegram_id=999, device_type="iOS", period_months=3, amount=400)
            )


class TestDeleteDevice:
    async def test_deletes_device_and_returns_name(
        self,
        interactor: DeviceInteractor,
        mock_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ) -> None:
        device = _make_device(device_name="iPhone 2500")
        mock_gateway.get_by_id.return_value = device

        name = await interactor.delete_device(DeleteDevice(device_id=1))

        mock_gateway.delete.assert_called_once_with(device)
        mock_uow.commit.assert_called_once()
        assert name == "iPhone 2500"

    async def test_raises_if_device_not_found(
        self,
        interactor: DeviceInteractor,
        mock_gateway: AsyncMock,
    ) -> None:
        mock_gateway.get_by_id.return_value = None

        with pytest.raises(DeviceNotFound):
            await interactor.delete_device(DeleteDevice(device_id=999))


class TestRenewSubscription:
    async def test_extends_active_subscription_from_end_date(
        self,
        interactor: DeviceInteractor,
        mock_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        future_end = now + timedelta(days=15)  # подписка ещё активна
        device = _make_device(end_date=future_end)
        mock_gateway.get_by_name.return_value = device

        result = await interactor.renew_subscription(
            RenewSubscription(device_name="Android 1000", period_months=1, amount=150)
        )

        # end_date должен быть future_end + 1 месяц, а не now + 1 месяц
        assert result.end_date > future_end

    async def test_restarts_expired_subscription_from_now(
        self,
        interactor: DeviceInteractor,
        mock_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        expired_end = now - timedelta(days=5)  # подписка истекла
        device = _make_device(end_date=expired_end)
        mock_gateway.get_by_name.return_value = device

        result = await interactor.renew_subscription(
            RenewSubscription(device_name="Android 1000", period_months=1, amount=150)
        )

        # end_date должен быть ~now + 1 месяц
        expected_min = now + timedelta(days=28)
        assert result.end_date > expected_min

    async def test_raises_if_device_not_found(
        self,
        interactor: DeviceInteractor,
        mock_gateway: AsyncMock,
    ) -> None:
        mock_gateway.get_by_name.return_value = None

        with pytest.raises(DeviceNotFound):
            await interactor.renew_subscription(
                RenewSubscription(device_name="unknown", period_months=1, amount=150)
            )

    async def test_raises_if_no_subscription(
        self,
        interactor: DeviceInteractor,
        mock_gateway: AsyncMock,
    ) -> None:
        device = Device(id=1, user_id=111, device_name="Test", subscription=None)
        mock_gateway.get_by_name.return_value = device

        with pytest.raises(SubscriptionNotFound):
            await interactor.renew_subscription(
                RenewSubscription(device_name="Test", period_months=1, amount=150)
            )


@pytest.mark.asyncio
async def test_create_device_deducts_balance_atomically(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    """balance_to_deduct > 0 — списание в том же commit что и создание устройства."""
    user = User(telegram_id=123, balance=100)
    mock_user_gateway.get_by_telegram_id.return_value = user
    mock_gateway.get_next_seq.return_value = 1

    cmd = CreateDevice(
        telegram_id=123,
        device_type="Android",
        period_months=1,
        amount=150,
        balance_to_deduct=50,
    )
    result = await interactor.create_device(cmd)

    assert user.balance == 50
    mock_uow.commit.assert_called_once()
    assert result.device_name.startswith("Android")


@pytest.mark.asyncio
async def test_create_device_raises_when_insufficient_balance(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    """Если balance_to_deduct > user.balance — поднимаем InsufficientBalance."""
    user = User(telegram_id=123, balance=30)
    mock_user_gateway.get_by_telegram_id.return_value = user
    mock_gateway.get_next_seq.return_value = 1

    cmd = CreateDevice(
        telegram_id=123,
        device_type="Android",
        period_months=1,
        amount=150,
        balance_to_deduct=50,
    )
    with pytest.raises(InsufficientBalance):
        await interactor.create_device(cmd)

    mock_uow.commit.assert_not_called()


@pytest.mark.asyncio
async def test_renew_subscription_deducts_balance_atomically(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    """renew_subscription: balance deduction и продление в одном commit."""
    sub = Subscription(device_id=1, plan=1, start_date=datetime.now(UTC), end_date=datetime.now(UTC))
    device = Device(user_id=123, device_name="Android 1", created_at=datetime.now(UTC), subscription=sub)
    mock_gateway.get_by_name.return_value = device

    user = User(telegram_id=123, balance=100)
    mock_user_gateway.get_by_telegram_id.return_value = user

    cmd = RenewSubscription(device_name="Android 1", period_months=1, amount=150, balance_to_deduct=30)
    result = await interactor.renew_subscription(cmd)

    assert user.balance == 70
    mock_uow.commit.assert_called_once()
    assert result.device_name == "Android 1"


@pytest.mark.asyncio
async def test_create_device_zero_balance_deduct_no_user_save(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    """balance_to_deduct == 0 — user.save не вызывается."""
    user = User(telegram_id=123, balance=100)
    mock_user_gateway.get_by_telegram_id.return_value = user
    mock_gateway.get_next_seq.return_value = 1

    cmd = CreateDevice(
        telegram_id=123,
        device_type="Android",
        period_months=1,
        amount=150,
        balance_to_deduct=0,
    )
    await interactor.create_device(cmd)

    assert user.balance == 100  # не изменился
    mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_pending_payment_saves_and_returns(
    interactor: DeviceInteractor,
    mock_pending_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
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


@pytest.mark.asyncio
async def test_confirm_payment_raises_if_not_found(
    interactor: DeviceInteractor,
    mock_pending_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    mock_pending_gateway.get_by_id.return_value = None

    with pytest.raises(PendingPaymentNotFound):
        await interactor.confirm_payment(ConfirmPayment(pending_id=999))


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
    call_kwargs = mock_remnawave_gateway.create_user.call_args.kwargs
    assert call_kwargs["telegram_id"] == 123
    assert call_kwargs["device_limit"] == 1
    assert call_kwargs["expire_at"] > datetime.now(UTC)


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
    assert call_kwargs["expire_at"] > datetime.now(UTC)
    assert result.subscription_url == "https://sub.test/url"
