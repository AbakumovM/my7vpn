import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.apps.auth.application.interfaces.email_sender import EmailSender
from src.apps.auth.application.interfaces.gateway import AuthGateway
from src.apps.auth.domain.commands import CreateBotToken, RequestOtp, VerifyBotToken, VerifyOtp
from src.apps.auth.domain.exceptions import (
    BotTokenExpired,
    BotTokenInvalid,
    OtpExpired,
    OtpInvalid,
)
from src.apps.auth.domain.models import BotAuthToken, OtpCode
from src.apps.user.application.interfaces.gateway import UserGateway
from src.apps.user.domain.models import User
from src.infrastructure.auth import create_jwt
from src.infrastructure.config import app_config
from src.infrastructure.database.uow import SQLAlchemyUoW


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    user_id: int


class AuthInteractor:
    def __init__(
        self,
        auth_gateway: AuthGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        email_sender: EmailSender,
    ) -> None:
        self._auth_gateway = auth_gateway
        self._user_gateway = user_gateway
        self._uow = uow
        self._email_sender = email_sender

    async def request_otp(self, cmd: RequestOtp) -> None:
        now = datetime.now(UTC)
        code = f"{secrets.randbelow(1000000):06d}"
        otp = OtpCode(
            email=cmd.email,
            code=code,
            created_at=now,
            expires_at=now + timedelta(minutes=app_config.auth.otp_expire_minutes),
        )
        await self._auth_gateway.save_otp(otp)
        await self._uow.commit()
        await self._email_sender.send_otp(cmd.email, code)

    async def verify_otp(self, cmd: VerifyOtp) -> AuthResult:
        otp = await self._auth_gateway.get_otp(cmd.email, cmd.code)
        if otp is None:
            raise OtpInvalid(cmd.email)

        now = datetime.now(UTC)
        if otp.expires_at.replace(tzinfo=UTC) < now:
            raise OtpExpired(cmd.email)

        await self._auth_gateway.mark_otp_used(otp)

        # Найти или создать пользователя по email
        user = await self._user_gateway.get_by_email(cmd.email)
        if user is None:
            user = User(email=cmd.email)
            await self._user_gateway.save(user)

        await self._uow.commit()

        # Получаем user_id из БД (после save/flush у нас есть id)
        user = await self._user_gateway.get_by_email(cmd.email)
        assert user is not None

        # Нужен внутренний id, получаем через view
        from sqlalchemy import select  # noqa: PLC0415, E402

        from src.apps.user.adapters.orm import UserORM  # noqa: PLC0415

        result = await self._uow._session.execute(
            select(UserORM.id).where(UserORM.email == cmd.email)
        )
        db_user_id: int = result.scalar_one()

        token = create_jwt(db_user_id)
        return AuthResult(access_token=token, user_id=db_user_id)

    async def create_bot_token(self, cmd: CreateBotToken) -> str:
        now = datetime.now(UTC)
        token_str = uuid.uuid4().hex
        token = BotAuthToken(
            user_id=cmd.user_id,
            token=token_str,
            created_at=now,
            expires_at=now + timedelta(minutes=app_config.auth.bot_token_expire_minutes),
        )
        await self._auth_gateway.save_bot_token(token)
        await self._uow.commit()
        return token_str

    async def verify_bot_token(self, cmd: VerifyBotToken) -> AuthResult:
        token = await self._auth_gateway.get_bot_token(cmd.token)
        if token is None:
            raise BotTokenInvalid(cmd.token)

        now = datetime.now(UTC)
        if token.expires_at.replace(tzinfo=UTC) < now:
            raise BotTokenExpired(cmd.token)

        await self._auth_gateway.mark_bot_token_used(token)
        await self._uow.commit()

        jwt_token = create_jwt(token.user_id)
        return AuthResult(access_token=jwt_token, user_id=token.user_id)
