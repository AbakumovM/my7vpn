from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.apps.device.adapters.orm import DeviceORM, PaymentORM, SubscriptionORM
from src.apps.device.domain.models import Device, Subscription
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
            created_at=row.created_at,
            subscription=sub,
        )
