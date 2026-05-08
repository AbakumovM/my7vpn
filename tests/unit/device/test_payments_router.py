import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from dishka import Provider, Scope, provide
from dishka.integrations.fastapi import setup_dishka
from unittest.mock import AsyncMock

from src.apps.device.application.interactor import DeviceInteractor, PendingPaymentInfo
from src.apps.device.application.interfaces.view import DeviceView, PendingStatusResult
from src.apps.user.application.interfaces.view import UserView
from src.apps.device.controllers.http.payments_router import router
from src.infrastructure.auth import create_jwt


def _make_jwt(user_id: int = 42) -> str:
    return create_jwt(user_id)


@pytest.fixture
def mock_interactor():
    m = AsyncMock(spec=DeviceInteractor)
    m.create_pending_payment.return_value = PendingPaymentInfo(
        id=1, user_id=42, action="new", device_type="vpn",
        device_name=None, duration=1, amount=0,
    )
    return m


@pytest.fixture
def mock_user_view():
    m = AsyncMock(spec=UserView)
    m.get_balance_by_user_id.return_value = 999  # more than any tariff
    return m


@pytest.fixture
def mock_device_view():
    return AsyncMock(spec=DeviceView)


@pytest.fixture
def app(mock_interactor, mock_user_view, mock_device_view):
    class MockProvider(Provider):
        scope = Scope.REQUEST

        @provide
        def interactor(self) -> DeviceInteractor:
            return mock_interactor

        @provide
        def user_view_dep(self) -> UserView:
            return mock_user_view

        @provide
        def device_view_dep(self) -> DeviceView:
            return mock_device_view

    _app = FastAPI()
    from dishka import make_async_container
    container = make_async_container(MockProvider())
    setup_dishka(container, app=_app)
    _app.include_router(router)
    return _app


@pytest.mark.asyncio
async def test_initiate_payment_zero_final_amount(app, mock_interactor, mock_user_view):
    """balance covers full amount → payment_url is null."""
    token = _make_jwt(42)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/payments/initiate",
            json={"action": "new", "plan": 1, "device_limit": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_id"] == 1
    assert data["amount"] == 150       # TARIFF_MATRIX[1][1]
    assert data["balance_used"] == 150
    assert data["final_amount"] == 0
    assert data["payment_url"] is None


@pytest.mark.asyncio
async def test_initiate_payment_invalid_plan_returns_422(app):
    """Invalid plan value returns 422."""
    token = _make_jwt(42)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/payments/initiate",
            json={"action": "new", "plan": 99, "device_limit": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_confirm_payment_not_found_returns_404(app, mock_device_view):
    """Returns 404 when pending_id not found or not owned by user."""
    mock_device_view.get_pending_status.return_value = None
    token = _make_jwt(42)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/payments/999/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_pending_status_pending(app, mock_device_view):
    """Returns status=pending when payment still awaiting."""
    mock_device_view.get_pending_status.return_value = PendingStatusResult(
        status="pending", subscription_url=None, end_date=None
    )
    token = _make_jwt(42)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/payments/1/status",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["subscription_url"] is None
    assert data["end_date"] is None


@pytest.mark.asyncio
async def test_get_payment_history_empty(app, mock_device_view):
    """Returns empty list when no payment history."""
    mock_device_view.get_payment_history.return_value = []
    token = _make_jwt(42)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/payments/history",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json() == []
