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
