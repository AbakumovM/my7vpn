from dataclasses import dataclass


@dataclass(frozen=True)
class CreateDevice:
    telegram_id: int
    device_type: str
    period_months: int
    amount: int
    balance_to_deduct: int = 0
    device_limit: int = 1
    vpn_config: str | None = None


@dataclass(frozen=True)
class CreateDeviceFree:
    telegram_id: int
    device_type: str
    period_days: int


@dataclass(frozen=True)
class DeleteDevice:
    device_id: int


@dataclass(frozen=True)
class RenewSubscription:
    device_name: str
    period_months: int
    amount: int
    balance_to_deduct: int = 0
    device_limit: int = 1


@dataclass(frozen=True)
class GetExpiringSubscriptions:
    pass


@dataclass(frozen=True)
class CreatePendingPayment:
    user_telegram_id: int
    action: str            # "new" | "renew"
    device_type: str
    duration: int
    amount: int
    balance_to_deduct: int
    device_limit: int = 1
    device_name: str | None = None  # None для new, имя для renew


@dataclass(frozen=True)
class ConfirmPayment:
    pending_id: int


@dataclass(frozen=True)
class RejectPayment:
    pending_id: int
