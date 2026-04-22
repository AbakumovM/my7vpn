import time
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
import uvicorn
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI, Request, Response

from ioc import create_container
from src.apps.auth.controllers.http.router import router as auth_router
from src.apps.device.controllers.http.router import router as device_router
from src.apps.device.controllers.http.yookassa_router import router as yookassa_router
from src.apps.user.controllers.http.router import router as user_router
from src.infrastructure.config import app_config
from src.infrastructure.logging.setup import configure_logging

configure_logging(app_config.logging)

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot = Bot(
        token=app_config.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    app.state.bot = bot
    yield
    await bot.session.close()


app = FastAPI(title="VPN Bot API", version="1.0.0", lifespan=lifespan)

container = create_container(app_config)
setup_dishka(container, app=app)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(device_router)
app.include_router(yookassa_router)


@app.middleware("http")
async def logging_middleware(request: Request, call_next) -> Response:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=str(uuid4()),
        method=request.method,
        path=request.url.path,
    )
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000)
    log.info("http_request", status=response.status_code, duration_ms=duration_ms)
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main_web:app", host="0.0.0.0", port=8000, log_config=None)
