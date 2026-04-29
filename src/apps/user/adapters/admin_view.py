from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import DeviceORM, SubscriptionORM, UserSubscriptionORM
from src.apps.user.adapters.orm import UserORM
from src.apps.user.application.interfaces.admin_view import (
    AdminChurn,
    AdminExpiring,
    AdminStats,
    AdminUserInfo,
)


class SQLAlchemyAdminView:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_stats(self) -> AdminStats:
        now = datetime.now(UTC)
        today = datetime.now(UTC).date()

        total = await self._session.scalar(select(func.count(UserORM.id))) or 0

        active = await self._session.scalar(
            select(func.count(UserSubscriptionORM.id)).where(
                UserSubscriptionORM.is_active.is_(True),
                UserSubscriptionORM.end_date > now,
            )
        ) or 0

        new_today = await self._session.scalar(
            select(func.count(UserORM.id)).where(UserORM.created_at == today)
        ) or 0

        new_week = await self._session.scalar(
            select(func.count(UserORM.id)).where(
                UserORM.created_at >= today - timedelta(days=7)
            )
        ) or 0

        new_month = await self._session.scalar(
            select(func.count(UserORM.id)).where(
                UserORM.created_at >= today - timedelta(days=30)
            )
        ) or 0

        return AdminStats(
            total_users=total,
            active_subscribers=active,
            new_today=new_today,
            new_week=new_week,
            new_month=new_month,
        )

    async def get_expiring(self) -> AdminExpiring:
        now = datetime.now(UTC)

        def count_expiring(days: int):
            return (
                select(func.count(UserSubscriptionORM.id))
                .where(
                    UserSubscriptionORM.is_active.is_(True),
                    UserSubscriptionORM.end_date > now,
                    UserSubscriptionORM.end_date <= now + timedelta(days=days),
                )
            )

        exp_3 = await self._session.scalar(count_expiring(3)) or 0
        exp_7 = await self._session.scalar(count_expiring(7)) or 0
        exp_30 = await self._session.scalar(count_expiring(30)) or 0

        return AdminExpiring(expiring_3d=exp_3, expiring_7d=exp_7, expiring_30d=exp_30)

    async def get_churn(self) -> AdminChurn:
        now = datetime.now(UTC)

        active_user_ids = (
            select(UserSubscriptionORM.user_id)
            .where(
                UserSubscriptionORM.is_active.is_(True),
                UserSubscriptionORM.end_date > now,
            )
            .scalar_subquery()
        )

        def count_churned(days: int):
            return (
                select(func.count(func.distinct(UserSubscriptionORM.user_id)))
                .where(
                    UserSubscriptionORM.end_date < now,
                    UserSubscriptionORM.end_date >= now - timedelta(days=days),
                    UserSubscriptionORM.user_id.not_in(active_user_ids),
                )
            )

        churned_7 = await self._session.scalar(count_churned(7)) or 0
        churned_30 = await self._session.scalar(count_churned(30)) or 0

        total_expired_30 = await self._session.scalar(
            select(func.count(func.distinct(UserSubscriptionORM.user_id))).where(
                UserSubscriptionORM.end_date < now,
                UserSubscriptionORM.end_date >= now - timedelta(days=30),
            )
        ) or 0

        if total_expired_30 > 0:
            renewed_30 = total_expired_30 - churned_30
            renewal_rate = round(renewed_30 / total_expired_30 * 100)
        else:
            renewal_rate = 0

        return AdminChurn(
            churned_7d=churned_7,
            churned_30d=churned_30,
            renewal_rate_30d=renewal_rate,
        )

    async def get_user_info(self, telegram_id: int) -> AdminUserInfo | None:
        user_row = await self._session.execute(
            select(UserORM).where(UserORM.telegram_id == telegram_id)
        )
        user = user_row.scalar_one_or_none()
        if user is None:
            return None

        sub_row = await self._session.execute(
            select(UserSubscriptionORM)
            .where(
                UserSubscriptionORM.user_id == user.id,
                UserSubscriptionORM.is_active.is_(True),
                UserSubscriptionORM.end_date > datetime.now(UTC),
            )
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        sub = sub_row.scalar_one_or_none()

        if sub is None:
            legacy_row = await self._session.execute(
                select(SubscriptionORM)
                .join(DeviceORM, SubscriptionORM.device_id == DeviceORM.id)
                .where(
                    DeviceORM.user_id == user.id,
                    SubscriptionORM.is_active.is_(True),
                    SubscriptionORM.end_date > datetime.now(UTC),
                )
                .order_by(SubscriptionORM.end_date.desc())
                .limit(1)
            )
            legacy_sub = legacy_row.scalar_one_or_none()
            active_until = legacy_sub.end_date if legacy_sub else None
            device_limit = None
        else:
            active_until = sub.end_date
            device_limit = sub.device_limit

        return AdminUserInfo(
            telegram_id=telegram_id,
            balance=user.balance or 0,
            referred_by=user.referred_by,
            active_until=active_until,
            device_limit=device_limit,
        )
