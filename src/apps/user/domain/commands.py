from dataclasses import dataclass


@dataclass(frozen=True)
class GetOrCreateUser:
    telegram_id: int
    referred_by_code: str | None = None


@dataclass(frozen=True)
class GetReferralCode:
    telegram_id: int


@dataclass(frozen=True)
class AddReferralBonus:
    referrer_telegram_id: int
    amount: int = 50


@dataclass(frozen=True)
class DeductUserBalance:
    telegram_id: int
    amount: int


@dataclass(frozen=True)
class MarkFreeMonthUsed:
    telegram_id: int
