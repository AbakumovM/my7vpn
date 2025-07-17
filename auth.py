from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, func, select
from db import AsyncSessionLocal, Device, Subscription, User, Payment
from dateutil.relativedelta import relativedelta
import logging
import random
from sqlalchemy.orm import joinedload


from utils.utl import generate_referral_code

logger = logging.getLogger(__name__)


async def get_or_create_user(telegram_id: int, referral_by: int = None):
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalars().first()
            if not user:
                referral = generate_referral_code(telegram_id)
                # free_month = True if referral_by else False
                referral_by_inbd = referral_by or None
                user = User(
                    telegram_id=telegram_id,
                    referral_code=referral,
                    referred_by=referral_by_inbd,
                )
                session.add(user)
                await session.commit()
            return user


async def get_user(telegram_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalars().first()
        return user or None


async def create_vpn(
    telegram_id: int,
    device: str,
    period: str = None,
    tariff: str = None,
    free_month: bool = False,
):
    try:
        logger.info(f"Creating VPN for user {telegram_id} with device {device}")
        async with AsyncSessionLocal() as session:
            async with session.begin():
                user = await session.scalar(
                    select(User).where(User.telegram_id == telegram_id)
                )
                if free_month:
                    user.free_months = free_month
                    await session.flush()
                device_id_last = await session.scalar(select(func.max(Device.id)))

                device_name = (
                    f"{device} {str(device_id_last + 1)}{random.randint(1, 5000)}"
                    if device_id_last
                    else f"{device} 1{random.randint(1, 5000)}"
                )
                device = Device(user_id=user.id, device_name=device_name)
                session.add(device)
                await session.flush()
                logger.info(f"Device created: {device.device_name}")

                period = 1 if free_month and period is None else period
                sub = Subscription(
                    device_id=device.id,
                    plan=int(period),
                    start_date=datetime.now(timezone.utc),
                    end_date=datetime.now(timezone.utc)
                    + relativedelta(months=int(period)),
                )
                session.add(sub)
                await session.flush()
                logger.info(f"Subscription created: {sub}")

                pay = Payment(
                    subscription_id=sub.id, amount=0 if free_month else int(tariff), payment_date=datetime.now(timezone.utc)
                )
                session.add(pay)
                await session.commit()
                logger.info(f"Payment created: {pay}")
                return device_name, user

    except Exception as e:
        logger.error(f"Error creating VPN for user {telegram_id}: {e}")
        raise


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
                .where(
                        Device.id == device_id
                    )
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


async def get_referral_by_id(referral: str):
    async with AsyncSessionLocal() as session:
        try:
            user = await session.scalar(
                select(User).where(User.referral_code == referral)
            )
            return user.telegram_id if user else None
        except Exception as e:
            logger.error(f"Error get referral by id: {e}")
            raise


async def add_referral_bonus(ref_id):
    try:
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).where(User.telegram_id == ref_id))
            user.balance += 50
            await session.commit()
    except Exception as e:
        logger.error(f"Error add referral bonus: {e}")
        raise


async def get_referral_code(telegram_id: int):
    async with AsyncSessionLocal() as session:
        try:
            user = await session.scalar(
                select(User).where(User.telegram_id == telegram_id)
            )
            if user.referral_code is None:
                referral = generate_referral_code(telegram_id)
                user.referral_code = referral
                await session.commit()
                return referral
            return user.referral_code
        except Exception as e:
            logger.error(f"Error get referral code: {e}")
            raise


async def get_balance_user(telegram_id: int):
    async with AsyncSessionLocal() as session:
        try:
            balance = await session.scalar(
                select(User.balance).where(User.telegram_id == telegram_id)
            )
            return balance
        except Exception as e:
            logger.error(f"Error get balance user: {e}")
            raise


async def update_balance_user(telegram_id: int, amount: int, referral: bool = False):
    async with AsyncSessionLocal() as session:
        try:
            user = await session.scalar(
                select(User).where(User.telegram_id == telegram_id)
            )
            if referral:
                user.balance += amount
            else:
                user.balance = amount
            await session.commit()
        except Exception as e:
            logger.error(f"Error set balance user: {e}")
            raise

async def update_tariff_from_device(device_name, tariff, period, payment):
    async with AsyncSessionLocal() as session:

        query = (
            select(Device)
            .options(
                joinedload(Device.subscription).joinedload(Subscription.payments)  # Загружаем связи
            )
            .where(Device.device_name == device_name)
        )
        result = await session.execute(query)
        device = result.scalars().first()
        print(period)
        print(device.subscription.end_date)
        print(device.subscription.end_date + relativedelta(months=int(period)))
        
        
        if device:
            # Обновляем Subscription
            if device.subscription:
                device.subscription.end_date = device.subscription.end_date + relativedelta(months=int(period))
                device.subscription.plan = int(period)
                device.subscription.start_date = datetime.now(timezone.utc)
                
                # Обновляем Payment
                if device.subscription.payments:
                    device.subscription.payments.amount = int(payment)
                    device.subscription.payments.payment_date = datetime.now(timezone.utc)
        

            await session.commit()
            return True


        return False
