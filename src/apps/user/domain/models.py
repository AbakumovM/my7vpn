from dataclasses import dataclass, field
from datetime import date


@dataclass
class User:
    telegram_id: int | None = None
    email: str | None = None
    balance: int = 0
    free_months: bool = False
    referral_code: str | None = None
    referred_by: int | None = None
    remnawave_uuid: str | None = None
    subscription_url: str | None = None
    created_at: date = field(default_factory=date.today)
