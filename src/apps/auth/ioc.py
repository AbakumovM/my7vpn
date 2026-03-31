from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.auth.adapters.gateway import SQLAlchemyAuthGateway
from src.apps.auth.application.interactor import AuthInteractor
from src.apps.auth.application.interfaces.email_sender import EmailSender
from src.apps.auth.application.interfaces.gateway import AuthGateway
from src.apps.user.application.interfaces.gateway import UserGateway
from src.infrastructure.database.uow import SQLAlchemyUoW
from src.infrastructure.smtp import SmtpService


class AuthProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_gateway(self, session: AsyncSession) -> AuthGateway:
        return SQLAlchemyAuthGateway(session)

    @provide
    def get_email_sender(self) -> EmailSender:
        return SmtpService()

    @provide
    def get_interactor(
        self,
        auth_gateway: AuthGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        email_sender: EmailSender,
    ) -> AuthInteractor:
        return AuthInteractor(
            auth_gateway=auth_gateway,
            user_gateway=user_gateway,
            uow=uow,
            email_sender=email_sender,
        )
