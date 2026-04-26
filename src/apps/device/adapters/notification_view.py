from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import UserSubscriptionORM
from src.apps.device.application.interfaces.notification_view import ExpiringUserSubscriptionInfo
from src.apps.user.adapters.orm import UserORM


class SQLAlchemyNotificationView:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_subscriptions_to_notify(
        self, days_offsets: list[int]
    ) -> list[ExpiringUserSubscriptionInfo]:
        today = date.today()
        target_dates = {offset: today + timedelta(days=offset) for offset in days_offsets}

        conditions = [
            func.date(UserSubscriptionORM.end_date) == target_date
            for target_date in target_dates.values()
        ]

        result = await self._session.execute(
            select(
                UserORM.id,
                UserORM.telegram_id,
                UserSubscriptionORM.end_date,
            )
            .join(UserSubscriptionORM, UserSubscriptionORM.user_id == UserORM.id)
            .where(or_(*conditions))
            .where(UserSubscriptionORM.is_active.is_(True))
        )

        date_to_days: dict[date, int] = {v: k for k, v in target_dates.items()}

        items: list[ExpiringUserSubscriptionInfo] = []
        for row in result:
            end_as_date = row.end_date.date() if hasattr(row.end_date, "date") else row.end_date
            days_before = date_to_days.get(end_as_date, 0)
            items.append(
                ExpiringUserSubscriptionInfo(
                    user_id=row.id,
                    telegram_id=row.telegram_id,
                    end_date=end_as_date,
                    days_before=days_before,
                )
            )
        return items
