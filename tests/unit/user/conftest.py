import pytest
from unittest.mock import AsyncMock

from src.apps.user.application.interfaces.gateway import UserGateway
from src.apps.user.application.interactor import UserInteractor
from src.infrastructure.database.uow import SQLAlchemyUoW


@pytest.fixture
def mock_gateway() -> AsyncMock:
    return AsyncMock(spec=UserGateway)


@pytest.fixture
def mock_uow() -> AsyncMock:
    return AsyncMock(spec=SQLAlchemyUoW)


@pytest.fixture
def interactor(mock_gateway: AsyncMock, mock_uow: AsyncMock) -> UserInteractor:
    return UserInteractor(gateway=mock_gateway, uow=mock_uow)
