from datetime import datetime

from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveUserInfo
from src.infrastructure.remnawave.client import RemnawaveApiUser, RemnawaveClient


class RemnawaveGatewayImpl:
    def __init__(self, client: RemnawaveClient) -> None:
        self._client = client

    def _map(self, raw: RemnawaveApiUser) -> RemnawaveUserInfo:
        return RemnawaveUserInfo(
            uuid=raw.uuid,
            username=raw.username,
            subscription_url=raw.subscription_url,
            expire_at=datetime.fromisoformat(raw.expire_at.replace("Z", "+00:00")),
            status=raw.status,
            hwid_device_limit=raw.hwid_device_limit,
            telegram_id=raw.telegram_id,
        )

    async def create_user(
        self, telegram_id: int, expire_at: datetime, device_limit: int
    ) -> RemnawaveUserInfo:
        raw = await self._client.create_user(
            telegram_id=telegram_id, expire_at=expire_at, device_limit=device_limit
        )
        return self._map(raw)

    async def update_user(
        self,
        uuid: str,
        expire_at: datetime | None = None,
        device_limit: int | None = None,
    ) -> RemnawaveUserInfo:
        raw = await self._client.update_user(
            uuid=uuid, expire_at=expire_at, device_limit=device_limit
        )
        return self._map(raw)

    async def delete_user(self, uuid: str) -> None:
        await self._client.delete_user(uuid)

    async def get_user_by_telegram_id(
        self, telegram_id: int
    ) -> RemnawaveUserInfo | None:
        raw = await self._client.get_user_by_telegram_id(telegram_id)
        if raw is None:
            return None
        return self._map(raw)

    async def enable_user(self, uuid: str) -> None:
        await self._client.enable_user(uuid)

    async def disable_user(self, uuid: str) -> None:
        await self._client.disable_user(uuid)
