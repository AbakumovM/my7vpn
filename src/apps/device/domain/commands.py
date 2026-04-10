from dataclasses import dataclass


@dataclass(frozen=True)
class CreateDevice:
    telegram_id: int
    device_type: str
    period_months: int
    amount: int
    balance_to_deduct: int = 0


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


@dataclass(frozen=True)
class GetExpiringSubscriptions:
    pass
