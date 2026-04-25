from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.user.adapters.orm import UserORM
from src.apps.user.application.interfaces.view import ReferralStats


class SQLAlchemyUserView:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_balance(self, telegram_id: int) -> int:
        result = await self._session.execute(
            select(UserORM.balance).where(UserORM.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none() or 0

    async def get_referral_code(self, telegram_id: int) -> str | None:
        result = await self._session.execute(
            select(UserORM.referral_code).where(UserORM.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_device_count(self, telegram_id: int) -> int:
        # импорт здесь чтобы избежать циклических зависимостей
        from src.apps.device.adapters.orm import DeviceORM  # noqa: PLC0415

        result = await self._session.execute(
            select(func.count(DeviceORM.id))
            .join(UserORM, DeviceORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id)
        )
        return result.scalar_one() or 0

    async def get_email(self, telegram_id: int) -> str | None:
        result = await self._session.execute(
            select(UserORM.email).where(UserORM.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_user_id(self, telegram_id: int) -> int | None:
        result = await self._session.execute(
            select(UserORM.id).where(UserORM.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_telegram_id(self, user_id: int) -> int | None:
        result = await self._session.execute(
            select(UserORM.telegram_id).where(UserORM.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_remnawave_uuid(self, telegram_id: int) -> str | None:
        result = await self._session.execute(
            select(UserORM.remnawave_uuid).where(UserORM.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_referral_stats(self, telegram_id: int) -> ReferralStats:
        count_result = await self._session.execute(
            select(func.count(UserORM.id)).where(UserORM.referred_by == telegram_id)
        )
        invited_count = count_result.scalar_one() or 0

        balance_result = await self._session.execute(
            select(UserORM.balance).where(UserORM.telegram_id == telegram_id)
        )
        balance = balance_result.scalar_one_or_none() or 0

        return ReferralStats(
            invited_count=invited_count,
            total_earned=invited_count * 50,
            balance=balance,
        )
