from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class DeviceSummary:
    id: int
    device_name: str


@dataclass(frozen=True)
class DeviceDetailInfo:
    device_name: str
    end_date: str
    amount: int
    payment_date: str


@dataclass(frozen=True)
class SubscriptionInfo:
    end_date: datetime | None
    device_limit: int
    last_payment_amount: int | None
    subscription_url: str | None


@dataclass(frozen=True)
class PaymentHistoryItem:
    id: int
    amount: int
    date: datetime
    plan: int
    device_limit: int
    payment_method: str
    status: str


@dataclass(frozen=True)
class PendingStatusResult:
    status: str                    # "pending" | "confirmed" | "rejected"
    subscription_url: str | None
    end_date: datetime | None


class DeviceView(Protocol):
    async def list_for_user(self, telegram_id: int) -> list[DeviceSummary]: ...

    async def list_for_user_by_id(self, user_id: int) -> list[DeviceSummary]: ...

    async def get_full_info(self, device_id: int) -> DeviceDetailInfo | None: ...

    async def get_subscription_info(self, telegram_id: int) -> SubscriptionInfo | None: ...

    async def get_payment_history(self, user_id: int) -> list[PaymentHistoryItem]: ...

    async def get_pending_status(
        self, pending_id: int, user_id: int
    ) -> PendingStatusResult | None: ...
