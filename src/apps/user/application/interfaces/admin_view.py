from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class AdminStats:
    total_users: int
    active_subscribers: int
    new_today: int
    new_week: int
    new_month: int


@dataclass(frozen=True)
class AdminExpiring:
    expiring_3d: int
    expiring_7d: int
    expiring_30d: int


@dataclass(frozen=True)
class AdminChurn:
    churned_7d: int
    churned_30d: int
    renewal_rate_30d: int  # процент 0–100


@dataclass(frozen=True)
class AdminUserInfo:
    telegram_id: int
    balance: int
    referred_by: int | None
    active_until: datetime | None
    device_limit: int | None


class AdminView(Protocol):
    async def get_stats(self) -> AdminStats: ...
    async def get_expiring(self) -> AdminExpiring: ...
    async def get_churn(self) -> AdminChurn: ...
    async def get_user_info(self, telegram_id: int) -> AdminUserInfo | None: ...
