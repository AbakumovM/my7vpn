from dataclasses import dataclass, field
from datetime import UTC, datetime


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
    payment_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    currency: str = "RUB"
    payment_method: str = "карта"
    id: int | None = None


@dataclass
class Device:
    user_id: int
    device_name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    vpn_config: str | None = None
    vpn_client_uuid: str | None = None
    id: int | None = None
    subscription: Subscription | None = None


@dataclass
class PendingPayment:
    user_telegram_id: int
    action: str                   # "new" | "renew"
    device_type: str              # "Android", "iOS", "TV", "Windows", "MacOS"
    duration: int                 # месяцев
    amount: int                   # к оплате
    balance_to_deduct: int
    created_at: datetime
    device_name: str | None = None  # None для new, имя устройства для renew
    id: int | None = None
