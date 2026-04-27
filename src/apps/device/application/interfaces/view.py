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


class DeviceView(Protocol):
    async def list_for_user(self, telegram_id: int) -> list[DeviceSummary]: ...

    async def list_for_user_by_id(self, user_id: int) -> list[DeviceSummary]: ...

    async def get_full_info(self, device_id: int) -> DeviceDetailInfo | None: ...

    async def get_subscription_info(self, telegram_id: int) -> SubscriptionInfo | None: ...
