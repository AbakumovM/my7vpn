from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Subscription:
    device_id: int
    plan: int
    start_date: datetime
    end_date: datetime
    is_active: bool = True
    id: int | None = None


@dataclass
class Payment:
    subscription_id: int
    amount: int
    payment_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    currency: str = "RUB"
    payment_method: str = "карта"
    id: int | None = None


@dataclass
class Device:
    user_id: int
    device_name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    vpn_config: str | None = None
    id: int | None = None
    subscription: Subscription | None = None
