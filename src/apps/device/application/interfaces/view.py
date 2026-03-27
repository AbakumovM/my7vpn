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
class ExpiringSubscriptionInfo:
    telegram_id: int
    device_name: str
    plan: int
    start_date: datetime
    end_date: datetime


class DeviceView(Protocol):
    async def list_for_user(self, telegram_id: int) -> list[DeviceSummary]: ...

    async def get_full_info(self, device_id: int) -> DeviceDetailInfo | None: ...

    async def get_expiring_today(self) -> list[ExpiringSubscriptionInfo]: ...
