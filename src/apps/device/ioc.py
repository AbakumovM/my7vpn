from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.gateway import SQLAlchemyDeviceGateway
from src.apps.device.adapters.view import SQLAlchemyDeviceView
from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.device.application.interactor import DeviceInteractor
from src.apps.user.application.interfaces.gateway import UserGateway
from src.infrastructure.database.uow import SQLAlchemyUoW


class DeviceProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_gateway(self, session: AsyncSession) -> DeviceGateway:
        return SQLAlchemyDeviceGateway(session)

    @provide
    def get_view(self, session: AsyncSession) -> DeviceView:
        return SQLAlchemyDeviceView(session)

    @provide
    def get_interactor(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
    ) -> DeviceInteractor:
        return DeviceInteractor(gateway=gateway, user_gateway=user_gateway, uow=uow)
