from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.auth.adapters.orm import BotAuthTokenORM, OtpCodeORM
from src.apps.auth.domain.models import BotAuthToken, OtpCode


class SQLAlchemyAuthGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_otp(self, otp: OtpCode) -> None:
        row = OtpCodeORM(
            email=otp.email,
            code=otp.code,
            created_at=otp.created_at,
            expires_at=otp.expires_at,
            is_used=otp.is_used,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_otp(self, email: str, code: str) -> OtpCode | None:
        result = await self._session.execute(
            select(OtpCodeORM)
            .where(
                OtpCodeORM.email == email,
                OtpCodeORM.code == code,
                OtpCodeORM.is_used.is_(False),
            )
            .order_by(OtpCodeORM.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return OtpCode(
            id=row.id,
            email=row.email,
            code=row.code,
            created_at=row.created_at,
            expires_at=row.expires_at,
            is_used=row.is_used,
        )

    async def mark_otp_used(self, otp: OtpCode) -> None:
        result = await self._session.execute(select(OtpCodeORM).where(OtpCodeORM.id == otp.id))
        row = result.scalar_one()
        row.is_used = True
        await self._session.flush()

    async def save_bot_token(self, token: BotAuthToken) -> None:
        row = BotAuthTokenORM(
            user_id=token.user_id,
            token=token.token,
            created_at=token.created_at,
            expires_at=token.expires_at,
            is_used=token.is_used,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_bot_token(self, token: str) -> BotAuthToken | None:
        result = await self._session.execute(
            select(BotAuthTokenORM).where(
                BotAuthTokenORM.token == token,
                BotAuthTokenORM.is_used.is_(False),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return BotAuthToken(
            id=row.id,
            user_id=row.user_id,
            token=row.token,
            created_at=row.created_at,
            expires_at=row.expires_at,
            is_used=row.is_used,
        )

    async def mark_bot_token_used(self, token: BotAuthToken) -> None:
        result = await self._session.execute(
            select(BotAuthTokenORM).where(BotAuthTokenORM.id == token.id)
        )
        row = result.scalar_one()
        row.is_used = True
        await self._session.flush()
