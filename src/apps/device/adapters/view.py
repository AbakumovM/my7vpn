from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import DeviceORM, PaymentORM, SubscriptionORM
from src.apps.device.application.interfaces.view import (
    DeviceDetailInfo,
    DeviceSummary,
    ExpiringSubscriptionInfo,
    SubscriptionInfo,
)
from src.apps.user.adapters.orm import UserORM


class SQLAlchemyDeviceView:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, telegram_id: int) -> list[DeviceSummary]:
        result = await self._session.execute(
            select(DeviceORM.id, DeviceORM.device_name)
            .join(UserORM, DeviceORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id)
        )
        return [DeviceSummary(id=row.id, device_name=row.device_name) for row in result]

    async def list_for_user_by_id(self, user_id: int) -> list[DeviceSummary]:
        result = await self._session.execute(
            select(DeviceORM.id, DeviceORM.device_name).where(DeviceORM.user_id == user_id)
        )
        return [DeviceSummary(id=row.id, device_name=row.device_name) for row in result]

    async def get_full_info(self, device_id: int) -> DeviceDetailInfo | None:
        result = await self._session.execute(
            select(
                DeviceORM.device_name,
                SubscriptionORM.end_date,
                PaymentORM.amount,
                PaymentORM.payment_date,
            )
            .join(SubscriptionORM, DeviceORM.id == SubscriptionORM.device_id)
            .join(PaymentORM, SubscriptionORM.id == PaymentORM.subscription_id)
            .where(DeviceORM.id == device_id)
            .order_by(PaymentORM.payment_date.desc())
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None
        device_name, end_date, amount, payment_date = row
        return DeviceDetailInfo(
            device_name=device_name,
            end_date=end_date.strftime("%d.%m.%Y") if end_date else "",
            amount=amount,
            payment_date=payment_date.strftime("%d.%m.%Y") if payment_date else "",
        )

    async def get_subscription_info(self, telegram_id: int) -> SubscriptionInfo | None:
        result = await self._session.execute(
            select(
                SubscriptionORM.end_date,
                DeviceORM.device_limit,
                UserORM.subscription_url,
            )
            .join(DeviceORM, SubscriptionORM.device_id == DeviceORM.id)
            .join(UserORM, DeviceORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id)
            .where(SubscriptionORM.is_active.is_(True))
            .order_by(SubscriptionORM.end_date.desc())
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None

        payment_result = await self._session.execute(
            select(PaymentORM.amount)
            .join(SubscriptionORM, PaymentORM.subscription_id == SubscriptionORM.id)
            .join(DeviceORM, SubscriptionORM.device_id == DeviceORM.id)
            .join(UserORM, DeviceORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id)
            .order_by(PaymentORM.payment_date.desc())
            .limit(1)
        )
        last_amount = payment_result.scalar_one_or_none()

        return SubscriptionInfo(
            end_date=row.end_date,
            device_limit=row.device_limit,
            last_payment_amount=last_amount,
            subscription_url=row.subscription_url,
        )

    async def get_expiring_today(self) -> list[ExpiringSubscriptionInfo]:
        today = date.today()
        result = await self._session.execute(
            select(
                UserORM.telegram_id,
                DeviceORM.device_name,
                SubscriptionORM.plan,
                SubscriptionORM.start_date,
                SubscriptionORM.end_date,
            )
            .join(DeviceORM, UserORM.id == DeviceORM.user_id)
            .join(SubscriptionORM, DeviceORM.id == SubscriptionORM.device_id)
            .where(func.date(SubscriptionORM.end_date) == today)
        )
        return [
            ExpiringSubscriptionInfo(
                telegram_id=row.telegram_id,
                device_name=row.device_name,
                plan=row.plan,
                start_date=row.start_date,
                end_date=row.end_date,
            )
            for row in result
        ]
