from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import structlog

from src.infrastructure.config import RemnawaveSettings

log = structlog.get_logger(__name__)


class RemnawaveAPIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Remnawave API error {status_code}: {detail}")


@dataclass
class RemnawaveApiUser:
    uuid: str
    username: str
    subscription_url: str
    expire_at: str   # raw ISO string from API — парсинг в адаптере
    status: str
    hwid_device_limit: int | None
    telegram_id: int | None


class RemnawaveClient:
    def __init__(self, settings: RemnawaveSettings) -> None:
        self._settings = settings

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.token}",
            "Content-Type": "application/json",
        }

    def _parse_user(self, data: dict) -> RemnawaveApiUser:  # type: ignore[type-arg]
        return RemnawaveApiUser(
            uuid=data["uuid"],
            username=data["username"],
            subscription_url=data["subscriptionUrl"],
            expire_at=data["expireAt"],
            status=data["status"],
            hwid_device_limit=data.get("hwidDeviceLimit"),
            telegram_id=data.get("telegramId"),
        )

    async def create_user(
        self,
        telegram_id: int,
        expire_at: datetime,
        device_limit: int,
    ) -> RemnawaveApiUser:
        payload = {
            "username": f"tg{telegram_id}",
            "expireAt": expire_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "hwidDeviceLimit": device_limit,
            "telegramId": telegram_id,
            "trafficLimitBytes": 0,
        }
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.post("/api/users", json=payload, headers=self._headers())
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
            data = resp.json()["response"]
        log.info("remnawave_user_created", telegram_id=telegram_id, uuid=data["uuid"])
        return self._parse_user(data)
