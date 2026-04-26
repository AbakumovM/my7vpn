from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.notification_view import SQLAlchemyNotificationView
from src.apps.device.application.interfaces.notification_view import ExpiringUserSubscriptionInfo


pytestmark = pytest.mark.asyncio


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def view(session: AsyncMock) -> SQLAlchemyNotificationView:
    return SQLAlchemyNotificationView(session)


def _make_row(user_id: int, telegram_id: int, end_date: date) -> MagicMock:
    row = MagicMock()
    row.id = user_id
    row.telegram_id = telegram_id
    # SQLAlchemy возвращает datetime с timezone для DateTime(timezone=True)
    row.end_date = datetime(end_date.year, end_date.month, end_date.day, tzinfo=timezone.utc)
    return row


async def test_get_subscriptions_to_notify_returns_correct_days_before(
    view: SQLAlchemyNotificationView, session: AsyncMock
) -> None:
    today = date.today()
    end_in_7 = today + timedelta(days=7)
    end_in_1 = today + timedelta(days=1)

    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([
        _make_row(user_id=1, telegram_id=100, end_date=end_in_7),
        _make_row(user_id=2, telegram_id=200, end_date=end_in_1),
    ]))
    session.execute = AsyncMock(return_value=mock_result)

    result = await view.get_subscriptions_to_notify([7, 3, 1, 0])

    assert len(result) == 2
    item_7 = next(r for r in result if r.user_id == 1)
    item_1 = next(r for r in result if r.user_id == 2)
    assert item_7.days_before == 7
    assert item_7.end_date == end_in_7
    assert item_1.days_before == 1
    assert item_1.end_date == end_in_1


async def test_get_subscriptions_to_notify_returns_empty_when_no_subscriptions(
    view: SQLAlchemyNotificationView, session: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    session.execute = AsyncMock(return_value=mock_result)

    result = await view.get_subscriptions_to_notify([7, 3, 1, 0])

    assert result == []
