from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.user.adapters.gateway import SQLAlchemyUserGateway
from src.apps.user.adapters.view import SQLAlchemyUserView
from src.apps.user.application.interfaces.gateway import UserGateway
from src.apps.user.application.interfaces.view import UserView
from src.apps.user.application.interactor import UserInteractor
from src.infrastructure.database.uow import SQLAlchemyUoW


class UserProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_gateway(self, session: AsyncSession) -> UserGateway:
        return SQLAlchemyUserGateway(session)

    @provide
    def get_view(self, session: AsyncSession) -> UserView:
        return SQLAlchemyUserView(session)

    @provide
    def get_interactor(self, gateway: UserGateway, uow: SQLAlchemyUoW) -> UserInteractor:
        return UserInteractor(gateway=gateway, uow=uow)
