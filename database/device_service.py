import logging
from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from database.models import AsyncSessionLocal, Device, Payment, Subscription, User

logger = logging.getLogger(__name__)


async def get_devices_users(telegram_id: int):
    try:
        async with AsyncSessionLocal() as session:
            user = await session.scalar(
                select(User).where(User.telegram_id == telegram_id)
            )
            result = await session.execute(
                select(Device).where(Device.user_id == user.id)
            )
            return result.scalars().all()
    except Exception as e:
        logger.error(f"Error get devices for user {user.id}: {e}")
        raise


async def del_device(id: int):
    async with AsyncSessionLocal() as session:
        async with session.begin():
            try:
                result = await session.execute(select(Device).where(Device.id == id))
                device = result.scalars().first()
                device_name = device.device_name
                await session.delete(device)
                await session.commit()
                return device_name
            except Exception as e:
                logger.error(f"Error delete device for user: {e}")
                raise


async def get_count_device_for_user(telegram_id: int):
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalars().first()
            result_dev = await session.execute(
                select(func.count(Device.id)).where(Device.user_id == user.id)
            )
            return result_dev.scalar()
    except Exception as e:
        logger.error(f"Error get devices: {e}")
        raise


async def get_full_info_device(device_id: int):
    try:
        async with AsyncSessionLocal() as session:
            query = (
                select(
                    Device.device_name,
                    Subscription.end_date,
                    Payment.amount,
                    Payment.payment_date,
                )
                .join(Subscription, Device.id == Subscription.device_id)
                .join(Payment, Subscription.id == Payment.subscription_id)
                .where(Device.id == device_id)
            )

            result = await session.execute(query)
            data = result.first()

            device_name, end_date, amount, payment_date = data

            return {
                "device_name": device_name,
                "end_date": end_date.strftime("%d.%m.%Y") if end_date else None,
                "amount": amount,
                "payment_date": (
                    payment_date.strftime("%d.%m.%Y") if payment_date else None
                ),
            }
    except Exception as e:
        logger.error(f"Error get full info devices: {e}")
        raise


async def update_tariff_from_device(device_name: str, period: int, payment: int):
    async with AsyncSessionLocal() as session:

        query = (
            select(Device)
            .options(
                joinedload(Device.subscription).joinedload(
                    Subscription.payments
                )  # Загружаем связи
            )
            .where(Device.device_name == device_name)
        )
        result = await session.execute(query)
        device = result.scalars().first()

        if device:
            # Обновляем Subscription
            if device.subscription:
                end_date = (
                    datetime.now(timezone.utc) + relativedelta(months=period)
                    if device.subscription.end_date < datetime.now(timezone.utc)
                    else device.subscription.end_date
                    + relativedelta(months=int(period))
                )
                device.subscription.end_date = end_date
                device.subscription.plan = period
                device.subscription.start_date = datetime.now(timezone.utc)

                # Обновляем Payment
                if device.subscription.payments:
                    last_payments = device.subscription.payments[-1]
                    last_payments.amount = payment
                    last_payments.payment_date = datetime.now(timezone.utc)

            await session.commit()
            return True

        return False
