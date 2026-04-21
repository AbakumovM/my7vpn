from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.gateway import (
    SQLAlchemyDeviceGateway,
    SQLAlchemyPendingPaymentGateway,
)
from src.apps.device.adapters.remnawave_gateway import RemnawaveGatewayImpl
from src.apps.device.adapters.view import SQLAlchemyDeviceView
from src.apps.device.application.interactor import DeviceInteractor
from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.user.application.interfaces.gateway import UserGateway
from src.infrastructure.config import AppConfig
from src.infrastructure.database.uow import SQLAlchemyUoW
from src.infrastructure.remnawave.client import RemnawaveClient


class DeviceProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_gateway(self, session: AsyncSession) -> DeviceGateway:
        return SQLAlchemyDeviceGateway(session)

    @provide
    def get_pending_gateway(self, session: AsyncSession) -> PendingPaymentGateway:
        return SQLAlchemyPendingPaymentGateway(session)

    @provide
    def get_view(self, session: AsyncSession) -> DeviceView:
        return SQLAlchemyDeviceView(session)

    @provide(scope=Scope.APP)
    def get_remnawave_client(self, config: AppConfig) -> RemnawaveClient:
        return RemnawaveClient(config.remnawave)

    @provide
    def get_remnawave_gateway(self, client: RemnawaveClient) -> RemnawaveGateway:
        # Registered for upcoming Remnawave bot flow integration (Etap 2, step 3+)
        return RemnawaveGatewayImpl(client)

    @provide
    def get_interactor(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        pending_gateway: PendingPaymentGateway,
    ) -> DeviceInteractor:
        return DeviceInteractor(
            gateway=gateway,
            user_gateway=user_gateway,
            uow=uow,
            pending_gateway=pending_gateway,
        )
