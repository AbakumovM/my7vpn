import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.apps.device.adapters.migration_view import SQLAlchemyMigrationView


@pytest.fixture
def session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_returns_users_with_old_subscriptions(session):
    """Возвращает пользователей с remnawave_uuid IS NULL и активной подпиской."""
    now = datetime.now(UTC)
    future = now + timedelta(days=10)

    row1 = MagicMock()
    row1.id = 1
    row1.telegram_id = 111
    row1.end_date = future

    row2 = MagicMock()
    row2.id = 2
    row2.telegram_id = 222
    row2.end_date = future + timedelta(days=5)

    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([row1, row2]))
    session.execute = AsyncMock(return_value=mock_result)

    view = SQLAlchemyMigrationView(session)
    result = await view.get_users_for_migration()

    assert len(result) == 2
    assert result[0].telegram_id == 111
    assert result[0].end_date == future
    assert result[1].telegram_id == 222


@pytest.mark.asyncio
async def test_returns_empty_when_no_users(session):
    """Возвращает пустой список если нет подходящих пользователей."""
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    session.execute = AsyncMock(return_value=mock_result)

    view = SQLAlchemyMigrationView(session)
    result = await view.get_users_for_migration()

    assert result == []
