from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import DeviceORM, SubscriptionORM
from src.apps.device.application.interfaces.migration_view import UserForMigrationInfo
from src.apps.user.adapters.orm import UserORM


class SQLAlchemyMigrationView:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_users_for_migration(self) -> list[UserForMigrationInfo]:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(
                UserORM.id,
                UserORM.telegram_id,
                SubscriptionORM.end_date,
            )
            .join(DeviceORM, DeviceORM.user_id == UserORM.id)
            .join(SubscriptionORM, SubscriptionORM.device_id == DeviceORM.id)
            .where(UserORM.remnawave_uuid.is_(None))
            .where(SubscriptionORM.is_active.is_(True))
            .where(SubscriptionORM.end_date > now)
            .distinct(UserORM.id)
            .order_by(UserORM.id, SubscriptionORM.end_date.desc())
        )
        return [
            UserForMigrationInfo(
                user_id=row.id,
                telegram_id=row.telegram_id,
                end_date=row.end_date,
            )
            for row in result
        ]
