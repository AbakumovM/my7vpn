import pytest
from unittest.mock import AsyncMock, MagicMock

from src.apps.device.adapters.view import SQLAlchemyDeviceView


@pytest.mark.asyncio
async def test_get_payment_history_returns_empty_for_unknown_user():
    """Returns empty list when no payments found."""
    session = AsyncMock()
    session.execute.return_value = MagicMock(all=MagicMock(return_value=[]))
    view = SQLAlchemyDeviceView(session)
    result = await view.get_payment_history(user_id=999)
    assert result == []


@pytest.mark.asyncio
async def test_get_pending_status_returns_none_for_unknown_pending():
    """Returns None when pending not found or not owned by user."""
    session = AsyncMock()
    session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    view = SQLAlchemyDeviceView(session)
    result = await view.get_pending_status(pending_id=999, user_id=42)
    assert result is None
