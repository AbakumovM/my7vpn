import pytest
from unittest.mock import AsyncMock, MagicMock
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
