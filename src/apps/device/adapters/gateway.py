from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.apps.device.adapters.orm import (
    DeviceORM,
    PaymentORM,
    PendingPaymentORM,
    SubscriptionORM,
    UserPaymentORM,
    UserSubscriptionORM,
)
from src.apps.device.domain.exceptions import SubscriptionNotFound
from src.apps.device.domain.models import (
    Device,
    PendingPayment,
    Subscription,
    UserPayment,
    UserSubscription,
)
from src.apps.user.adapters.orm import UserORM


class SQLAlchemyDeviceGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, device_id: int) -> Device | None:
        result = await self._session.execute(
            select(DeviceORM)
            .options(joinedload(DeviceORM.subscription).joinedload(SubscriptionORM.payments))
            .where(DeviceORM.id == device_id)
        )
        row = result.unique().scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_by_name(self, device_name: str) -> Device | None:
        result = await self._session.execute(
            select(DeviceORM)
            .options(joinedload(DeviceORM.subscription).joinedload(SubscriptionORM.payments))
            .where(DeviceORM.device_name == device_name)
        )
        row = result.unique().scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_active_by_telegram_id(self, telegram_id: int) -> Device | None:
        result = await self._session.execute(
            select(DeviceORM)
            .options(joinedload(DeviceORM.subscription).joinedload(SubscriptionORM.payments))
            .join(UserORM, DeviceORM.user_id == UserORM.id)
            .join(SubscriptionORM, DeviceORM.id == SubscriptionORM.device_id)
            .where(UserORM.telegram_id == telegram_id)
            .where(SubscriptionORM.is_active.is_(True))
            .order_by(SubscriptionORM.end_date.desc())
            .limit(1)
        )
        row = result.unique().scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_next_seq(self) -> int:
        result = await self._session.execute(select(func.max(DeviceORM.id)))
        max_id = result.scalar_one_or_none()
        return (max_id or 0) + 1

    async def save(self, device: Device) -> None:
        if device.id is None:
            # Создание нового устройства
            user_result = await self._session.execute(
                select(UserORM).where(UserORM.telegram_id == device.user_id)
            )
            user_orm = user_result.scalar_one()
            device_orm = DeviceORM(
                user_id=user_orm.id,
                device_name=device.device_name,
                created_at=device.created_at,
                vpn_config=device.vpn_config,
                vpn_client_uuid=device.vpn_client_uuid,
                device_limit=device.device_limit,
            )
            self._session.add(device_orm)
            await self._session.flush()

            if device.subscription is not None:
                sub = device.subscription
                sub_orm = SubscriptionORM(
                    device_id=device_orm.id,
                    plan=sub.plan,
                    start_date=sub.start_date,
                    end_date=sub.end_date,
                    is_active=sub.is_active,
                )
                self._session.add(sub_orm)
                await self._session.flush()

                payments = getattr(sub, "payments", [])
                for pay in payments:
                    pay_orm = PaymentORM(
                        subscription_id=sub_orm.id,
                        amount=pay.amount,
                        payment_date=pay.payment_date,
                        currency=pay.currency,
                        payment_method=pay.payment_method,
                    )
                    self._session.add(pay_orm)
                await self._session.flush()
        else:
            # Обновление существующего (продление подписки)
            result = await self._session.execute(
                select(DeviceORM)
                .options(joinedload(DeviceORM.subscription).joinedload(SubscriptionORM.payments))
                .where(DeviceORM.id == device.id)
            )
            device_orm = result.unique().scalar_one()

            device_orm.device_limit = device.device_limit

            if device.subscription and device_orm.subscription:
                sub = device.subscription
                device_orm.subscription.end_date = sub.end_date
                device_orm.subscription.plan = sub.plan
                device_orm.subscription.start_date = sub.start_date

                if device_orm.subscription.payments:
                    last = device_orm.subscription.payments[-1]
                    last.payment_date = datetime.now(UTC)

            await self._session.flush()

    async def delete(self, device: Device) -> None:
        if device.id is None:
            return
        result = await self._session.execute(select(DeviceORM).where(DeviceORM.id == device.id))
        device_orm = result.scalar_one_or_none()
        if device_orm:
            await self._session.delete(device_orm)
            await self._session.flush()

    async def get_active_subscription_end_date(self, telegram_id: int) -> datetime:
        result = await self._session.execute(
            select(SubscriptionORM.end_date)
            .join(DeviceORM, SubscriptionORM.device_id == DeviceORM.id)
            .join(UserORM, DeviceORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id)
            .where(SubscriptionORM.is_active.is_(True))
            .where(SubscriptionORM.end_date > datetime.now(UTC))
            .order_by(SubscriptionORM.end_date.desc())
            .limit(1)
        )
        end_date = result.scalar_one_or_none()
        if end_date is None:
            raise SubscriptionNotFound(telegram_id=telegram_id)
        return end_date

    @staticmethod
    def _to_domain(row: DeviceORM) -> Device:
        sub: Subscription | None = None
        if row.subscription:
            s = row.subscription
            sub = Subscription(
                id=s.id,
                device_id=s.device_id,
                plan=s.plan,
                start_date=s.start_date,
                end_date=s.end_date,
                is_active=s.is_active,
            )
        return Device(
            id=row.id,
            user_id=row.user_id,
            device_name=row.device_name,
            vpn_config=row.vpn_config,
            vpn_client_uuid=row.vpn_client_uuid,
            device_limit=row.device_limit,
            created_at=row.created_at,
            subscription=sub,
        )


class SQLAlchemyPendingPaymentGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, pending: PendingPayment) -> PendingPayment:
        if pending.id is None:
            orm = PendingPaymentORM(
                user_telegram_id=pending.user_telegram_id,
                action=pending.action,
                device_type=pending.device_type,
                device_name=pending.device_name,
                duration=pending.duration,
                amount=pending.amount,
                balance_to_deduct=pending.balance_to_deduct,
                device_limit=pending.device_limit,
                created_at=pending.created_at,
            )
            self._session.add(orm)
            await self._session.flush()
            pending.id = orm.id  # type: ignore[misc]
        return pending

    async def get_by_id(self, pending_id: int) -> PendingPayment | None:
        result = await self._session.execute(
            select(PendingPaymentORM).where(PendingPaymentORM.id == pending_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return PendingPayment(
            id=row.id,
            user_telegram_id=row.user_telegram_id,
            action=row.action,
            device_type=row.device_type,
            device_name=row.device_name,
            duration=row.duration,
            amount=row.amount,
            balance_to_deduct=row.balance_to_deduct,
            device_limit=row.device_limit,
            created_at=row.created_at,
        )

    async def delete(self, pending_id: int) -> None:
        result = await self._session.execute(
            select(PendingPaymentORM).where(PendingPaymentORM.id == pending_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()


class SQLAlchemySubscriptionGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_by_telegram_id(self, telegram_id: int) -> UserSubscription | None:
        result = await self._session.execute(
            select(UserSubscriptionORM)
            .join(UserORM, UserSubscriptionORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id)
            .where(UserSubscriptionORM.is_active.is_(True))
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UserSubscription(
            id=row.id,
            user_telegram_id=telegram_id,
            plan=row.plan,
            start_date=row.start_date,
            end_date=row.end_date,
            device_limit=row.device_limit,
            is_active=row.is_active,
        )

    async def save(self, sub: UserSubscription) -> UserSubscription:
        if sub.id is None:
            user_result = await self._session.execute(
                select(UserORM).where(UserORM.telegram_id == sub.user_telegram_id)
            )
            user_orm = user_result.scalar_one()
            orm = UserSubscriptionORM(
                user_id=user_orm.id,
                plan=sub.plan,
                start_date=sub.start_date,
                end_date=sub.end_date,
                device_limit=sub.device_limit,
                is_active=sub.is_active,
            )
            self._session.add(orm)
            await self._session.flush()
            sub.id = orm.id
        else:
            result = await self._session.execute(
                select(UserSubscriptionORM).where(UserSubscriptionORM.id == sub.id)
            )
            orm = result.scalar_one()
            orm.end_date = sub.end_date
            orm.device_limit = sub.device_limit
            orm.plan = sub.plan
            orm.start_date = sub.start_date
            await self._session.flush()
        return sub

    async def save_payment(self, payment: UserPayment) -> UserPayment:
        orm = UserPaymentORM(
            user_telegram_id=payment.user_telegram_id,
            subscription_id=payment.subscription_id,
            amount=payment.amount,
            duration=payment.duration,
            device_limit=payment.device_limit,
            payment_date=payment.payment_date,
            currency=payment.currency,
            payment_method=payment.payment_method,
            status=payment.status,
            external_id=payment.external_id,
        )
        self._session.add(orm)
        await self._session.flush()
        payment.id = orm.id  # type: ignore[misc]  # id set by ORM after flush
        return payment

    async def count_payments_for_user(self, telegram_id: int) -> int:
        result = await self._session.execute(
            select(func.count(UserPaymentORM.id))
            .where(UserPaymentORM.user_telegram_id == telegram_id)
            .where(UserPaymentORM.amount > 0)
        )
        return result.scalar_one()
