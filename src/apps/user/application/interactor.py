import hashlib
from dataclasses import dataclass

from src.apps.user.application.interfaces.gateway import UserGateway
from src.apps.user.domain.commands import (
    AddReferralBonus,
    DeductUserBalance,
    GetOrCreateUser,
    GetReferralCode,
    MarkFreeMonthUsed,
)
from src.apps.user.domain.exceptions import (
    InsufficientBalance,
    ReferralNotFound,
    UserNotFound,
)
from src.apps.user.domain.models import User
from src.infrastructure.database.uow import SQLAlchemyUoW


@dataclass(frozen=True)
class UserInfo:
    telegram_id: int
    balance: int
    free_months: bool
    referral_code: str | None


@dataclass(frozen=True)
class ReferralCodeInfo:
    telegram_id: int
    referral_code: str


def _generate_referral_code(telegram_id: int) -> str:
    return hashlib.md5(str(telegram_id).encode()).hexdigest()[:8]


class UserInteractor:
    def __init__(self, gateway: UserGateway, uow: SQLAlchemyUoW) -> None:
        self._gateway = gateway
        self._uow = uow

    async def get_or_create(self, cmd: GetOrCreateUser) -> UserInfo:
        user = await self._gateway.get_by_telegram_id(cmd.telegram_id)
        if user is not None:
            return UserInfo(
                telegram_id=user.telegram_id,
                balance=user.balance,
                free_months=user.free_months,
                referral_code=user.referral_code,
            )

        referred_by_id: int | None = None
        if cmd.referred_by_code is not None:
            referrer = await self._gateway.get_by_referral_code(cmd.referred_by_code)
            if referrer is None:
                raise ReferralNotFound(cmd.referred_by_code)
            referred_by_id = referrer.telegram_id

        user = User(
            telegram_id=cmd.telegram_id,
            referred_by=referred_by_id,
        )
        await self._gateway.save(user)
        await self._uow.commit()
        return UserInfo(
            telegram_id=user.telegram_id,
            balance=user.balance,
            free_months=user.free_months,
            referral_code=user.referral_code,
        )

    async def get_referral_code(self, cmd: GetReferralCode) -> ReferralCodeInfo:
        user = await self._gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserNotFound(cmd.telegram_id)

        if user.referral_code is None:
            user.referral_code = _generate_referral_code(cmd.telegram_id)
            await self._gateway.save(user)
            await self._uow.commit()

        return ReferralCodeInfo(
            telegram_id=user.telegram_id,
            referral_code=user.referral_code,  # type: ignore[arg-type]
        )

    async def add_referral_bonus(self, cmd: AddReferralBonus) -> UserInfo:
        user = await self._gateway.get_by_telegram_id(cmd.referrer_telegram_id)
        if user is None:
            raise UserNotFound(cmd.referrer_telegram_id)

        user.balance += cmd.amount  # всегда прибавляем, никогда не перезаписываем
        await self._gateway.save(user)
        await self._uow.commit()
        return UserInfo(
            telegram_id=user.telegram_id,
            balance=user.balance,
            free_months=user.free_months,
            referral_code=user.referral_code,
        )

    async def deduct_balance(self, cmd: DeductUserBalance) -> UserInfo:
        user = await self._gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserNotFound(cmd.telegram_id)
        if user.balance < cmd.amount:
            raise InsufficientBalance(cmd.telegram_id, user.balance, cmd.amount)

        user.balance -= cmd.amount  # исправление бага: -= вместо =
        await self._gateway.save(user)
        await self._uow.commit()
        return UserInfo(
            telegram_id=user.telegram_id,
            balance=user.balance,
            free_months=user.free_months,
            referral_code=user.referral_code,
        )

    async def mark_free_month_used(self, cmd: MarkFreeMonthUsed) -> UserInfo:
        user = await self._gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserNotFound(cmd.telegram_id)

        user.free_months = True
        await self._gateway.save(user)
        await self._uow.commit()
        return UserInfo(
            telegram_id=user.telegram_id,
            balance=user.balance,
            free_months=user.free_months,
            referral_code=user.referral_code,
        )
