from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import (
    DeviceORM,
    PaymentORM,
    SubscriptionORM,
    UserPaymentORM,
    UserSubscriptionORM,
)
from src.apps.device.application.interfaces.view import (
    DeviceDetailInfo,
    DeviceSummary,
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
        # Сначала проверяем новую модель (user_subscriptions)
        new_result = await self._session.execute(
            select(
                UserSubscriptionORM.end_date,
                UserSubscriptionORM.device_limit,
            )
            .join(UserORM, UserSubscriptionORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id)
            .where(UserSubscriptionORM.is_active.is_(True))
            .where(UserSubscriptionORM.end_date > datetime.now(UTC))
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        new_row = new_result.first()

        if new_row is not None:
            payment_result = await self._session.execute(
                select(UserPaymentORM.amount)
                .where(UserPaymentORM.user_telegram_id == telegram_id)
                .order_by(UserPaymentORM.payment_date.desc())
                .limit(1)
            )
            last_amount = payment_result.scalar_one_or_none()

            url_result = await self._session.execute(
                select(UserORM.subscription_url).where(UserORM.telegram_id == telegram_id)
            )
            subscription_url = url_result.scalar_one_or_none()

            return SubscriptionInfo(
                end_date=new_row.end_date,
                device_limit=new_row.device_limit,
                last_payment_amount=last_amount,
                subscription_url=subscription_url,
            )

        # Fallback: старая модель (devices → subscriptions)
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
            .where(SubscriptionORM.end_date > datetime.now(UTC))
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
