from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.notification_gateway import SQLAlchemyNotificationLogGateway


pytestmark = pytest.mark.asyncio


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def gateway(session: AsyncMock) -> SQLAlchemyNotificationLogGateway:
    return SQLAlchemyNotificationLogGateway(session)


async def test_is_sent_returns_true_when_record_exists(
    gateway: SQLAlchemyNotificationLogGateway, session: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 42  # id exists
    session.execute = AsyncMock(return_value=mock_result)

    result = await gateway.is_sent(user_id=1, days_before=7, sub_end_date=date(2026, 5, 1))

    assert result is True


async def test_is_sent_returns_false_when_no_record(
    gateway: SQLAlchemyNotificationLogGateway, session: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    result = await gateway.is_sent(user_id=1, days_before=7, sub_end_date=date(2026, 5, 1))

    assert result is False


async def test_mark_sent_executes_and_commits(
    gateway: SQLAlchemyNotificationLogGateway, session: AsyncMock
) -> None:
    await gateway.mark_sent(user_id=1, days_before=3, sub_end_date=date(2026, 5, 1))

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
