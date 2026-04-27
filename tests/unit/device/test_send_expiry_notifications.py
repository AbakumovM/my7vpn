# tests/unit/device/test_send_expiry_notifications.py
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.apps.device.application.interfaces.notification_gateway import NotificationLogGateway
from src.apps.device.application.interfaces.notification_view import (
    ExpiringUserSubscriptionInfo,
    NotificationView,
)
from src.common.scheduler.tasks import send_expiry_notifications

pytestmark = pytest.mark.asyncio


def _make_sub(user_id: int, telegram_id: int, days_before: int) -> ExpiringUserSubscriptionInfo:
    return ExpiringUserSubscriptionInfo(
        user_id=user_id,
        telegram_id=telegram_id,
        end_date=date.today() + timedelta(days=days_before),
        days_before=days_before,
    )


@pytest.fixture
def mock_bot() -> AsyncMock:
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_view() -> AsyncMock:
    return AsyncMock(spec=NotificationView)


@pytest.fixture
def mock_gateway() -> AsyncMock:
    return AsyncMock(spec=NotificationLogGateway)


@pytest.fixture
def mock_container(mock_view: AsyncMock, mock_gateway: AsyncMock) -> MagicMock:
    request_container = AsyncMock()
    request_container.get = AsyncMock(
        side_effect=lambda cls: {
            NotificationView: mock_view,
            NotificationLogGateway: mock_gateway,
        }[cls]
    )

    container = MagicMock()
    container.return_value.__aenter__ = AsyncMock(return_value=request_container)
    container.return_value.__aexit__ = AsyncMock(return_value=False)
    return container


async def test_sends_notification_when_not_sent(
    mock_bot: AsyncMock,
    mock_view: AsyncMock,
    mock_gateway: AsyncMock,
    mock_container: MagicMock,
) -> None:
    mock_view.get_subscriptions_to_notify = AsyncMock(
        return_value=[_make_sub(user_id=1, telegram_id=100, days_before=7)]
    )
    mock_gateway.is_sent = AsyncMock(return_value=False)
    mock_gateway.mark_sent = AsyncMock()

    await send_expiry_notifications(bot=mock_bot, container=mock_container)

    mock_bot.send_message.assert_awaited_once()
    call_kwargs = mock_bot.send_message.call_args
    assert call_kwargs.kwargs["chat_id"] == 100
    mock_gateway.mark_sent.assert_awaited_once_with(
        user_id=1,
        days_before=7,
        sub_end_date=_make_sub(1, 100, 7).end_date,
    )


async def test_skips_already_sent(
    mock_bot: AsyncMock,
    mock_view: AsyncMock,
    mock_gateway: AsyncMock,
    mock_container: MagicMock,
) -> None:
    mock_view.get_subscriptions_to_notify = AsyncMock(
        return_value=[_make_sub(user_id=1, telegram_id=100, days_before=3)]
    )
    mock_gateway.is_sent = AsyncMock(return_value=True)

    await send_expiry_notifications(bot=mock_bot, container=mock_container)

    mock_bot.send_message.assert_not_awaited()
    mock_gateway.mark_sent.assert_not_awaited()


async def test_continues_on_send_error(
    mock_bot: AsyncMock,
    mock_view: AsyncMock,
    mock_gateway: AsyncMock,
    mock_container: MagicMock,
) -> None:
    mock_view.get_subscriptions_to_notify = AsyncMock(
        return_value=[
            _make_sub(user_id=1, telegram_id=100, days_before=1),
            _make_sub(user_id=2, telegram_id=200, days_before=1),
        ]
    )
    mock_gateway.is_sent = AsyncMock(return_value=False)
    mock_gateway.mark_sent = AsyncMock()
    mock_bot.send_message = AsyncMock(side_effect=[Exception("blocked"), None])

    await send_expiry_notifications(bot=mock_bot, container=mock_container)

    assert mock_bot.send_message.await_count == 2
    # Только второй успешно отправлен — mark_sent вызван один раз
    mock_gateway.mark_sent.assert_awaited_once()
