from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import NotificationLogORM


class SQLAlchemyNotificationLogGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_sent(self, user_id: int, days_before: int, sub_end_date: date) -> bool:
        result = await self._session.execute(
            select(NotificationLogORM.id)
            .where(NotificationLogORM.user_id == user_id)
            .where(NotificationLogORM.days_before == days_before)
            .where(NotificationLogORM.sub_end_date == sub_end_date)
        )
        return result.scalar_one_or_none() is not None

    async def mark_sent(self, user_id: int, days_before: int, sub_end_date: date) -> None:
        stmt = (
            pg_insert(NotificationLogORM)
            .values(
                user_id=user_id,
                days_before=days_before,
                sub_end_date=sub_end_date,
                sent_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "days_before", "sub_end_date"]
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
