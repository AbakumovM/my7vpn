import httpx
import pytest
import respx

from src.infrastructure.config import YooKassaSettings
from src.infrastructure.yookassa.client import CreatedPayment, YooKassaAPIError, YooKassaClient

SETTINGS = YooKassaSettings(
    shop_id="123456",
    secret_key="test_secret",
    return_url="https://example.com/ok",
    enabled=True,
)


@pytest.mark.asyncio
@respx.mock
async def test_create_payment_returns_url() -> None:
    respx.post("https://api.yookassa.ru/v3/payments").mock(
        return_value=httpx.Response(200, json={
            "id": "pay-123",
            "confirmation": {"confirmation_url": "https://yookassa.ru/checkout/pay/abc"},
        })
    )
    result = await YooKassaClient(SETTINGS).create_payment(amount=150, pending_id=42)
    assert isinstance(result, CreatedPayment)
    assert result.payment_id == "pay-123"
    assert "yookassa.ru" in result.confirmation_url


@pytest.mark.asyncio
@respx.mock
async def test_create_payment_sends_metadata() -> None:
    route = respx.post("https://api.yookassa.ru/v3/payments").mock(
        return_value=httpx.Response(200, json={
            "id": "pay-456",
            "confirmation": {"confirmation_url": "https://yookassa.ru/checkout/pay/xyz"},
        })
    )
    await YooKassaClient(SETTINGS).create_payment(amount=400, pending_id=99)
    body = route.calls[0].request.read()
    import json
    payload = json.loads(body)
    assert payload["metadata"]["pending_id"] == "99"
    assert payload["amount"]["value"] == "400.00"
    assert payload["capture"] is True


@pytest.mark.asyncio
@respx.mock
async def test_create_payment_raises_on_error() -> None:
    respx.post("https://api.yookassa.ru/v3/payments").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    with pytest.raises(YooKassaAPIError) as exc_info:
        await YooKassaClient(SETTINGS).create_payment(amount=150, pending_id=42)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_get_payment_status_succeeded() -> None:
    respx.get("https://api.yookassa.ru/v3/payments/pay-123").mock(
        return_value=httpx.Response(200, json={"status": "succeeded"})
    )
    status = await YooKassaClient(SETTINGS).get_payment_status("pay-123")
    assert status == "succeeded"


@pytest.mark.asyncio
@respx.mock
async def test_get_payment_status_raises_on_error() -> None:
    respx.get("https://api.yookassa.ru/v3/payments/pay-bad").mock(
        return_value=httpx.Response(404, text="Not found")
    )
    with pytest.raises(YooKassaAPIError) as exc_info:
        await YooKassaClient(SETTINGS).get_payment_status("pay-bad")
    assert exc_info.value.status_code == 404
