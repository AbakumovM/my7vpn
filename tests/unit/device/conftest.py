import pytest
from unittest.mock import AsyncMock

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
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
def mock_remnawave_gateway() -> AsyncMock:
    return AsyncMock(spec=RemnawaveGateway)


@pytest.fixture
def interactor(
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_uow: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
) -> DeviceInteractor:
    return DeviceInteractor(
        gateway=mock_gateway,
        user_gateway=mock_user_gateway,
        uow=mock_uow,
        pending_gateway=mock_pending_gateway,
        remnawave_gateway=mock_remnawave_gateway,
    )
