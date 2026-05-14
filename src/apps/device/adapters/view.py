from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import (
    DeviceORM,
    PaymentORM,
    PendingPaymentORM,
    SubscriptionORM,
    UserPaymentORM,
    UserSubscriptionORM,
)
from src.apps.device.application.interfaces.view import (
    DeviceDetailInfo,
    DeviceSummary,
    PaymentHistoryItem,
    PendingStatusResult,
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

    async def get_subscription_info_by_user_id(self, user_id: int) -> SubscriptionInfo | None:
        """Works for both Telegram users and web-only users (no telegram_id needed)."""
        row_result = await self._session.execute(
            select(
                UserSubscriptionORM.end_date,
                UserSubscriptionORM.device_limit,
                UserORM.subscription_url,
            )
            .join(UserORM, UserSubscriptionORM.user_id == UserORM.id)
            .where(UserSubscriptionORM.user_id == user_id)
            .where(UserSubscriptionORM.is_active.is_(True))
            .where(UserSubscriptionORM.end_date > datetime.now(UTC))
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        row = row_result.first()
        if row is None:
            return None
        last_payment_result = await self._session.execute(
            select(UserPaymentORM.amount)
            .where(UserPaymentORM.user_id == user_id)
            .order_by(UserPaymentORM.payment_date.desc())
            .limit(1)
        )
        last_amount = last_payment_result.scalar_one_or_none()
        return SubscriptionInfo(
            end_date=row.end_date,
            device_limit=row.device_limit,
            last_payment_amount=last_amount,
            subscription_url=row.subscription_url,
        )

    async def get_payment_history(self, user_id: int) -> list[PaymentHistoryItem]:
        result = await self._session.execute(
            select(
                UserPaymentORM.id,
                UserPaymentORM.amount,
                UserPaymentORM.payment_date,
                UserPaymentORM.duration,
                UserPaymentORM.device_limit,
                UserPaymentORM.payment_method,
                UserPaymentORM.status,
            )
            .where(UserPaymentORM.user_id == user_id)
            .order_by(UserPaymentORM.payment_date.desc())
        )
        return [
            PaymentHistoryItem(
                id=row.id,
                amount=row.amount,
                date=row.payment_date,
                plan=row.duration,
                device_limit=row.device_limit,
                payment_method=row.payment_method or "карта",
                status=row.status,
            )
            for row in result.all()
        ]

    async def get_pending_status(
        self, pending_id: int, user_id: int
    ) -> PendingStatusResult | None:
        result = await self._session.execute(
            select(PendingPaymentORM.status)
            .where(PendingPaymentORM.id == pending_id)
            .where(PendingPaymentORM.user_id == user_id)
        )
        status = result.scalar_one_or_none()
        if status is None:
            return None

        if status in ("pending", "rejected"):
            return PendingStatusResult(status=status, subscription_url=None, end_date=None)

        # status == "confirmed" — look up current subscription data
        url_result = await self._session.execute(
            select(UserORM.subscription_url).where(UserORM.id == user_id)
        )
        subscription_url = url_result.scalar_one_or_none()

        sub_result = await self._session.execute(
            select(UserSubscriptionORM.end_date)
            .where(UserSubscriptionORM.user_id == user_id)
            .where(UserSubscriptionORM.is_active.is_(True))
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        end_date = sub_result.scalar_one_or_none()

        return PendingStatusResult(
            status="confirmed",
            subscription_url=subscription_url,
            end_date=end_date,
        )
