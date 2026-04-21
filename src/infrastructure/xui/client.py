import uuid as uuid_lib
from dataclasses import dataclass

import httpx
import structlog

log = structlog.get_logger(__name__)


@dataclass
class XuiSettings:
    url: str = ""
    username: str = ""
    password: str = ""
    inbound_id: int = 1
    vless_template: str = ""


class XuiClient:
    def __init__(self, settings: XuiSettings) -> None:
        self._settings = settings

    async def add_client(self, client_name: str) -> tuple[str, str]:
        """
        Логинится в 3x-ui, добавляет VLESS-клиента.

        Returns:
            (vless_link, client_uuid)

        Raises:
            httpx.HTTPStatusError: если 3x-ui вернул ошибку HTTP
            RuntimeError: если 3x-ui вернул success=False
        """
        client_uuid = str(uuid_lib.uuid4())
        s = self._settings

        async with httpx.AsyncClient(base_url=s.url, timeout=15.0) as http:
            login_resp = await http.post(
                "/login",
                data={"username": s.username, "password": s.password},
            )
            login_resp.raise_for_status()
            log.debug("xui_login_ok")

            payload = {
                "id": s.inbound_id,
                "settings": (
                    '{"clients": [{"id": "'
                    + client_uuid
                    + '", "email": "'
                    + client_name
                    + '", "enable": true, "expiryTime": 0}]}'
                ),
            }
            add_resp = await http.post("/panel/api/inbounds/addClient", json=payload)
            add_resp.raise_for_status()
            result = add_resp.json()
            if not result.get("success"):
                raise RuntimeError(f"3x-ui addClient failed: {result}")

        log.info("xui_client_added", client_name=client_name, uuid=client_uuid)
        return s.vless_template.format(uuid=client_uuid, name=client_name), client_uuid

    async def remove_client(self, client_uuid: str) -> None:
        """
        Логинится в 3x-ui и удаляет VLESS-клиента по UUID.

        Raises:
            httpx.HTTPStatusError: если 3x-ui вернул ошибку HTTP
            RuntimeError: если 3x-ui вернул success=False
        """
        s = self._settings

        async with httpx.AsyncClient(base_url=s.url, timeout=15.0) as http:
            login_resp = await http.post(
                "/login",
                data={"username": s.username, "password": s.password},
            )
            login_resp.raise_for_status()
            log.debug("xui_login_ok")

            del_resp = await http.post(
                f"/panel/api/inbounds/{s.inbound_id}/delClient/{client_uuid}"
            )
            del_resp.raise_for_status()
            result = del_resp.json()
            if not result.get("success"):
                raise RuntimeError(f"3x-ui delClient failed: {result}")

        log.info("xui_client_removed", uuid=client_uuid)
