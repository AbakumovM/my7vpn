import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from dishka.integrations.fastapi import setup_dishka
from unittest.mock import MagicMock

from src.apps.device.controllers.http.tariffs_router import router


@pytest.fixture
def app():
    _app = FastAPI()
    container = MagicMock()
    container.__aenter__ = MagicMock(return_value=container)
    container.__aexit__ = MagicMock(return_value=None)
    setup_dishka(container, app=_app)
    _app.include_router(router)
    return _app


@pytest.mark.asyncio
async def test_get_tariffs_no_auth(app):
    """GET /api/v1/tariffs returns tariff matrix without authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/tariffs")
    assert resp.status_code == 200
    data = resp.json()
    # verify the outer keys are device_limit strings
    assert "1" in data
    # verify inner keys are plan-month strings
    assert "3" in data["1"]
    # verify specific values from TARIFF_MATRIX
    assert data["1"]["1"] == 150
    assert data["2"]["3"] == 650
    assert data["3"]["12"] == 2600
