from dishka import AsyncContainer, make_async_container

from src.apps.device.ioc import DeviceProvider
from src.apps.user.ioc import UserProvider
from src.infrastructure.config import AppConfig
from src.infrastructure.database.provider import DatabaseProvider


def create_container(config: AppConfig) -> AsyncContainer:
    return make_async_container(
        DatabaseProvider(),
        UserProvider(),
        DeviceProvider(),
        context={AppConfig: config},
    )
