from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.infrastructure.xui.client import XuiClient
from src.infrastructure.config import XuiSettings


def make_client() -> XuiClient:
    settings = XuiSettings(
        url="http://localhost:57385/panel",
        username="admin",
        password="secret",
        inbound_id=1,
        vless_template="vless://{uuid}@host:443?params#{name}",
    )
    return XuiClient(settings)


@pytest.mark.asyncio
async def test_add_client_returns_vless_link() -> None:
    """add_client логинится, добавляет клиента, возвращает VLESS-ссылку."""
    client = make_client()

    mock_response_login = MagicMock()
    mock_response_login.raise_for_status = MagicMock()

    mock_response_add = MagicMock()
    mock_response_add.raise_for_status = MagicMock()
    mock_response_add.json.return_value = {"success": True}

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(side_effect=[mock_response_login, mock_response_add])
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)

    with patch("src.infrastructure.xui.client.httpx.AsyncClient", return_value=mock_http):
        link = await client.add_client("Android 11234")

    assert link.startswith("vless://")
    assert "Android 11234" in link
    assert mock_http.post.call_count == 2
