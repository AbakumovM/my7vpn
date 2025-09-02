import logging
import random
from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, select, text

from database.models import AsyncSessionLocal, Device, Payment, Subscription, User
from utils.utl import generate_referral_code

logger = logging.getLogger(__name__)


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
                    subscription_id=sub.id,
                    amount=0 if free_month else int(tariff),
                    payment_date=datetime.now(timezone.utc),
                )
                session.add(pay)
                await session.commit()
                logger.info(f"Payment created: {pay}")
                return device_name, user

    except Exception as e:
        logger.error(f"Error creating VPN for user {telegram_id}: {e}")
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


async def scheduled_payments():
    async with AsyncSessionLocal() as session:
        query = text(
            """select 
                        u.telegram_id,
                        d.device_name,
                        s.start_date,
                        s.end_date,
                        s.plan
                    from users u 
                    join devices d  on u.id = d.user_id
                    join subscriptions s on s.device_id = d.id
                    where s.end_date::date = current_date;"""
        )
        try:
            result = await session.execute(query)
            return result.fetchall()
        except Exception as e:
            logger.error(f"Error check payments: {e}")
