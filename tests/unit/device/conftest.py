import pytest
from unittest.mock import AsyncMock

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interactor import DeviceInteractor
from src.apps.user.application.interfaces.gateway import UserGateway
from src.infrastructure.database.uow import SQLAlchemyUoW


@pytest.fixture
def mock_gateway() -> AsyncMock:
    return AsyncMock(spec=DeviceGateway)


@pytest.fixture
def mock_user_gateway() -> AsyncMock:
    return AsyncMock(spec=UserGateway)


@pytest.fixture
def mock_uow() -> AsyncMock:
    return AsyncMock(spec=SQLAlchemyUoW)


@pytest.fixture
def mock_pending_gateway() -> AsyncMock:
    return AsyncMock(spec=PendingPaymentGateway)


@pytest.fixture
def mock_xui_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def interactor(
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_uow: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_xui_client: AsyncMock,
) -> DeviceInteractor:
    return DeviceInteractor(
        gateway=mock_gateway,
        user_gateway=mock_user_gateway,
        uow=mock_uow,
        pending_gateway=mock_pending_gateway,
        xui_client=mock_xui_client,
    )
