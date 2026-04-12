import uuid as uuid_lib

import httpx
import structlog

from src.infrastructure.config import XuiSettings

log = structlog.get_logger(__name__)


class XuiClient:
    def __init__(self, settings: XuiSettings) -> None:
        self._settings = settings

    async def add_client(self, client_name: str) -> str:
        """
        Логинится в 3x-ui, добавляет VLESS-клиента, возвращает ссылку подключения.

        Шаги:
        1. POST {url}/login — получить сессионную куку
        2. POST {url}/panel/api/inbounds/addClient — добавить клиента
        3. Подставить uuid + name в vless_template

        Raises:
            httpx.HTTPStatusError: если 3x-ui вернул ошибку HTTP
            RuntimeError: если 3x-ui вернул success=False
        """
        client_uuid = str(uuid_lib.uuid4())
        s = self._settings

        async with httpx.AsyncClient(base_url=s.url, timeout=15.0) as http:
            # 1. Логин
            login_resp = await http.post(
                "/login",
                data={"username": s.username, "password": s.password},
            )
            login_resp.raise_for_status()
            log.debug("xui_login_ok")

            # 2. Добавить клиента
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

        # 3. Сформировать VLESS-ссылку из шаблона
        return s.vless_template.format(uuid=client_uuid, name=client_name)
