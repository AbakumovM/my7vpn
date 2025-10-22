import logging

from sqlalchemy import select

from database.models import AsyncSessionLocal, User
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


async def update_balance_user(
    telegram_id: int, amount: int, referral: bool = False
) -> None:
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
