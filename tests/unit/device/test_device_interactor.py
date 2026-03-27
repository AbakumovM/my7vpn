from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.apps.device.application.interactor import DeviceInteractor
from src.apps.device.domain.commands import CreateDevice, DeleteDevice, RenewSubscription
from src.apps.device.domain.exceptions import DeviceNotFound, SubscriptionNotFound, UserDeviceNotFound
from src.apps.device.domain.models import Device, Subscription
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
