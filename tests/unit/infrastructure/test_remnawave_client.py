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


@respx.mock
@pytest.mark.asyncio
async def test_update_user_sends_patch_with_uuid() -> None:
    """update_user отправляет PATCH /api/users с uuid и expireAt."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    expire_at = datetime(2026, 1, 17, 15, 38, 45, tzinfo=timezone.utc)

    respx.patch(f"{BASE_URL}/api/users").mock(
        return_value=httpx.Response(200, json=make_user_response(
            expire_at="2026-01-17T15:38:45.000Z"
        ))
    )

    result = await client.update_user(
        uuid="550e8400-e29b-41d4-a716-446655440000",
        expire_at=expire_at,
    )

    assert result.uuid == "550e8400-e29b-41d4-a716-446655440000"


@respx.mock
@pytest.mark.asyncio
async def test_update_user_sends_only_provided_fields() -> None:
    """update_user не включает None-поля в payload."""
    settings = make_settings()
    client = RemnawaveClient(settings)

    route = respx.patch(f"{BASE_URL}/api/users").mock(
        return_value=httpx.Response(200, json=make_user_response())
    )

    await client.update_user(uuid="test-uuid", device_limit=5)

    payload = json.loads(route.calls.last.request.content)
    assert payload["uuid"] == "test-uuid"
    assert payload["hwidDeviceLimit"] == 5
    assert "expireAt" not in payload


@respx.mock
@pytest.mark.asyncio
async def test_delete_user_sends_delete_request() -> None:
    """delete_user отправляет DELETE /api/users/{uuid} без исключений."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    test_uuid = "550e8400-e29b-41d4-a716-446655440000"

    respx.delete(f"{BASE_URL}/api/users/{test_uuid}").mock(
        return_value=httpx.Response(200, json={"response": {"isDeleted": True}})
    )

    await client.delete_user(test_uuid)  # не должно бросать исключений


@respx.mock
@pytest.mark.asyncio
async def test_delete_user_raises_on_404() -> None:
    """delete_user бросает RemnawaveAPIError при 404."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    test_uuid = "nonexistent-uuid"

    respx.delete(f"{BASE_URL}/api/users/{test_uuid}").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    with pytest.raises(RemnawaveAPIError) as exc_info:
        await client.delete_user(test_uuid)

    assert exc_info.value.status_code == 404


@respx.mock
@pytest.mark.asyncio
async def test_get_user_by_telegram_id_returns_user() -> None:
    """get_user_by_telegram_id возвращает RemnawaveApiUser при 200."""
    settings = make_settings()
    client = RemnawaveClient(settings)

    respx.get(f"{BASE_URL}/api/users/by-telegram-id/123456789").mock(
        return_value=httpx.Response(200, json=make_user_response())
    )

    result = await client.get_user_by_telegram_id(123456789)

    assert result is not None
    assert result.uuid == "550e8400-e29b-41d4-a716-446655440000"


@respx.mock
@pytest.mark.asyncio
async def test_get_user_by_telegram_id_returns_none_on_404() -> None:
    """get_user_by_telegram_id возвращает None при 404 (пользователь не найден)."""
    settings = make_settings()
    client = RemnawaveClient(settings)

    respx.get(f"{BASE_URL}/api/users/by-telegram-id/999").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    result = await client.get_user_by_telegram_id(999)

    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_enable_user_sends_post_to_enable_endpoint() -> None:
    """enable_user отправляет POST /api/users/{uuid}/actions/enable."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    test_uuid = "550e8400-e29b-41d4-a716-446655440000"

    respx.post(f"{BASE_URL}/api/users/{test_uuid}/actions/enable").mock(
        return_value=httpx.Response(200, json=make_user_response(status="ACTIVE"))
    )

    await client.enable_user(test_uuid)  # не должно бросать исключений


@respx.mock
@pytest.mark.asyncio
async def test_disable_user_sends_post_to_disable_endpoint() -> None:
    """disable_user отправляет POST /api/users/{uuid}/actions/disable."""
    settings = make_settings()
    client = RemnawaveClient(settings)
    test_uuid = "550e8400-e29b-41d4-a716-446655440000"

    respx.post(f"{BASE_URL}/api/users/{test_uuid}/actions/disable").mock(
        return_value=httpx.Response(200, json=make_user_response(status="DISABLED"))
    )

    await client.disable_user(test_uuid)  # не должно бросать исключений
