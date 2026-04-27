from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ReferralStats:
    invited_count: int
    total_earned: int
    balance: int


class UserView(Protocol):
    async def get_balance(self, telegram_id: int) -> int: ...

    async def get_referral_code(self, telegram_id: int) -> str | None: ...

    async def get_device_count(self, telegram_id: int) -> int: ...

    async def get_email(self, telegram_id: int) -> str | None: ...

    async def get_user_id(self, telegram_id: int) -> int | None: ...

    async def get_telegram_id(self, user_id: int) -> int | None: ...

    async def get_referral_stats(self, telegram_id: int) -> ReferralStats: ...

    async def get_remnawave_uuid(self, telegram_id: int) -> str | None: ...

    async def get_referrer_telegram_id(self, referral_code: str) -> int | None:
        """Return telegram_id of the user who owns this referral code, or None."""
        ...
