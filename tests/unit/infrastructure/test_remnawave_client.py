import json
from datetime import datetime, timezone

import httpx
import pytest
import respx

from src.infrastructure.config import RemnawaveSettings
from src.infrastructure.remnawave.client import RemnawaveAPIError, RemnawaveApiUser, RemnawaveClient

BASE_URL = "https://panel.test.com"


def make_settings() -> RemnawaveSettings:
    return RemnawaveSettings(url=BASE_URL, token="test-token-abc")


def make_user_response(
    uuid: str = "550e8400-e29b-41d4-a716-446655440000",
    username: str = "tg123456789",
    subscription_url: str = "https://sub.test.com/api/sub/abc123",
    expire_at: str = "2025-07-17T15:38:45.000Z",
    status: str = "ACTIVE",
    hwid_device_limit: int | None = 3,
    telegram_id: int | None = 123456789,
) -> dict:
    return {
        "response": {
            "uuid": uuid,
            "username": username,
            "subscriptionUrl": subscription_url,
            "expireAt": expire_at,
            "status": status,
            "hwidDeviceLimit": hwid_device_limit,
            "telegramId": telegram_id,
        }
    }


@respx.mock
@pytest.mark.asyncio
async def test_create_user_returns_remnawave_api_user() -> None:
    """create_user отправляет POST /api/users и возвращает RemnawaveApiUser."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    expire_at = datetime(2025, 7, 17, 15, 38, 45, tzinfo=timezone.utc)

    respx.post(f"{BASE_URL}/api/users").mock(
        return_value=httpx.Response(201, json=make_user_response())
    )

    result = await client.create_user(telegram_id=123456789, expire_at=expire_at, device_limit=3)

    assert isinstance(result, RemnawaveApiUser)
    assert result.uuid == "550e8400-e29b-41d4-a716-446655440000"
    assert result.username == "tg123456789"
    assert result.subscription_url == "https://sub.test.com/api/sub/abc123"
    assert result.status == "ACTIVE"
    assert result.hwid_device_limit == 3
    assert result.telegram_id == 123456789


@respx.mock
@pytest.mark.asyncio
async def test_create_user_sends_correct_payload() -> None:
    """create_user отправляет username=tg{id}, trafficLimitBytes=0, hwidDeviceLimit."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    expire_at = datetime(2025, 7, 17, 15, 38, 45, tzinfo=timezone.utc)

    route = respx.post(f"{BASE_URL}/api/users").mock(
        return_value=httpx.Response(201, json=make_user_response())
    )

    await client.create_user(telegram_id=123456789, expire_at=expire_at, device_limit=3)

    sent = route.calls.last.request
    payload = json.loads(sent.content)
    assert payload["username"] == "tg123456789"
    assert payload["telegramId"] == 123456789
    assert payload["hwidDeviceLimit"] == 3
    assert payload["trafficLimitBytes"] == 0
    assert "expireAt" in payload


@respx.mock
@pytest.mark.asyncio
async def test_create_user_raises_api_error_on_500() -> None:
    """create_user бросает RemnawaveAPIError при ответе 500."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    expire_at = datetime(2025, 7, 17, 15, 38, 45, tzinfo=timezone.utc)

    respx.post(f"{BASE_URL}/api/users").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with pytest.raises(RemnawaveAPIError) as exc_info:
        await client.create_user(telegram_id=123456789, expire_at=expire_at, device_limit=3)

    assert exc_info.value.status_code == 500
