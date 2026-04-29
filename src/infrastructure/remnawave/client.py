from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import structlog

from src.infrastructure.config import RemnawaveSettings

log = structlog.get_logger(__name__)


class RemnawaveAPIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Remnawave API error {status_code}: {detail}")


@dataclass(frozen=True)
class RemnawaveHwidDevice:
    hwid: str
    platform: str | None
    os_version: str | None
    device_model: str | None
    created_at: datetime


@dataclass(frozen=True)
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

    def _parse_user(self, data: dict[str, object]) -> RemnawaveApiUser:
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
        payload: dict[str, object] = {
            "username": f"tg{telegram_id}",
            "expireAt": expire_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "hwidDeviceLimit": device_limit,
            "telegramId": telegram_id,
            "trafficLimitBytes": 0,
        }
        if self._settings.default_squad_uuid:
            payload["activeInternalSquads"] = [self._settings.default_squad_uuid]
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.post("/api/users", json=payload, headers=self._headers())
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
            data = resp.json()["response"]
        log.info("remnawave_user_created", telegram_id=telegram_id, uuid=data["uuid"])
        return self._parse_user(data)

    async def update_user(
        self,
        uuid: str,
        expire_at: datetime | None = None,
        device_limit: int | None = None,
    ) -> RemnawaveApiUser:
        payload: dict[str, object] = {"uuid": uuid}
        if expire_at is not None:
            payload["expireAt"] = expire_at.astimezone(UTC).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            )
        if device_limit is not None:
            payload["hwidDeviceLimit"] = device_limit
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.patch("/api/users", json=payload, headers=self._headers())
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
            data = resp.json()["response"]
        log.info("remnawave_user_updated", uuid=uuid)
        return self._parse_user(data)

    async def delete_user(self, uuid: str) -> None:
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.delete(f"/api/users/{uuid}", headers=self._headers())
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
        log.info("remnawave_user_deleted", uuid=uuid)

    async def get_user_by_telegram_id(self, telegram_id: int) -> RemnawaveApiUser | None:
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.get(
                f"/api/users/by-telegram-id/{telegram_id}", headers=self._headers()
            )
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
            data = resp.json()["response"]
        return self._parse_user(data)

    async def enable_user(self, uuid: str) -> None:
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.post(
                f"/api/users/{uuid}/actions/enable", headers=self._headers()
            )
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
        log.info("remnawave_user_enabled", uuid=uuid)

    async def disable_user(self, uuid: str) -> None:
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.post(
                f"/api/users/{uuid}/actions/disable", headers=self._headers()
            )
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
        log.info("remnawave_user_disabled", uuid=uuid)

    async def get_hwid_devices_count(self, uuid: str) -> int:
        """Возвращает количество зарегистрированных HWID-устройств пользователя."""
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.get(f"/api/hwid/devices/{uuid}", headers=self._headers())
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
        return resp.json()["response"]["total"]

    async def get_hwid_devices(self, uuid: str) -> list[RemnawaveHwidDevice]:
        """Возвращает список HWID-устройств с деталями."""
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.get(f"/api/hwid/devices/{uuid}", headers=self._headers())
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
        devices = resp.json()["response"]["devices"]
        return [
            RemnawaveHwidDevice(
                hwid=d["hwid"],
                platform=d.get("platform"),
                os_version=d.get("osVersion"),
                device_model=d.get("deviceModel"),
                created_at=datetime.fromisoformat(d["createdAt"].replace("Z", "+00:00")),
            )
            for d in devices
        ]

    async def delete_hwid_device(self, uuid: str, hwid: str) -> None:
        """Удаляет одно HWID-устройство пользователя."""
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.post(
                "/api/hwid/devices/delete",
                json={"userUuid": uuid, "hwid": hwid},
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
        log.info("remnawave_hwid_device_deleted", uuid=uuid, hwid=hwid)

    async def delete_all_hwid_devices(self, uuid: str) -> None:
        """Удаляет все HWID-устройства пользователя."""
        async with httpx.AsyncClient(base_url=self._settings.url, timeout=15.0) as http:
            resp = await http.post(
                "/api/hwid/devices/delete-all",
                json={"userUuid": uuid},
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                raise RemnawaveAPIError(resp.status_code, resp.text)
        log.info("remnawave_all_hwid_devices_deleted", uuid=uuid)
