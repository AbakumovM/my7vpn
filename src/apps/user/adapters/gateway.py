from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.user.adapters.orm import UserORM
from src.apps.user.domain.models import User


class SQLAlchemyUserGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.telegram_id == telegram_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserORM).where(UserORM.email == email))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    async def get_by_referral_code(self, referral_code: str) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.referral_code == referral_code)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    async def save(self, user: User) -> None:
        row: UserORM | None = None
        if user.telegram_id is not None:
            result = await self._session.execute(
                select(UserORM).where(UserORM.telegram_id == user.telegram_id)
            )
            row = result.scalar_one_or_none()
        if row is None and user.email is not None:
            result = await self._session.execute(select(UserORM).where(UserORM.email == user.email))
            row = result.scalar_one_or_none()
        if row is None:
            row = UserORM(telegram_id=user.telegram_id, email=user.email)
            self._session.add(row)
        row.telegram_id = user.telegram_id
        row.email = user.email
        row.balance = user.balance
        row.free_months = user.free_months
        row.referral_code = user.referral_code
        row.referred_by = user.referred_by
        row.remnawave_uuid = user.remnawave_uuid
        row.subscription_url = user.subscription_url
        await self._session.flush()

    @staticmethod
    def _to_domain(row: UserORM) -> User:
        return User(
            telegram_id=row.telegram_id,
            email=row.email,
            balance=row.balance,
            free_months=row.free_months,
            referral_code=row.referral_code,
            referred_by=row.referred_by,
            remnawave_uuid=row.remnawave_uuid,
            subscription_url=row.subscription_url,
            created_at=row.created_at,
        )
