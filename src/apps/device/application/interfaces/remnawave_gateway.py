from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class HwidDevice:
    hwid: str
    platform: str | None
    os_version: str | None
    device_model: str | None
    created_at: datetime


@dataclass(frozen=True)
class RemnawaveUserInfo:
    uuid: str
    username: str
    subscription_url: str
    expire_at: datetime
    status: str           # "ACTIVE" | "DISABLED" | "LIMITED" | "EXPIRED"
    hwid_device_limit: int | None
    telegram_id: int | None


class RemnawaveGateway(Protocol):
    async def create_user(
        self, telegram_id: int, expire_at: datetime, device_limit: int
    ) -> RemnawaveUserInfo: ...

    async def update_user(
        self,
        uuid: str,
        expire_at: datetime | None = None,
        device_limit: int | None = None,
    ) -> RemnawaveUserInfo: ...

    async def delete_user(self, uuid: str) -> None: ...

    async def get_user_by_telegram_id(
        self, telegram_id: int
    ) -> RemnawaveUserInfo | None: ...

    async def enable_user(self, uuid: str) -> None: ...

    async def disable_user(self, uuid: str) -> None: ...

    async def get_hwid_devices_count(self, uuid: str) -> int: ...

    async def get_hwid_devices(self, uuid: str) -> list[HwidDevice]: ...

    async def delete_hwid_device(self, uuid: str, hwid: str) -> None: ...

    async def delete_all_hwid_devices(self, uuid: str) -> None: ...
