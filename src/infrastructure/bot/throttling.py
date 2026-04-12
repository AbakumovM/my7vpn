import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

log = structlog.get_logger(__name__)

_RATE_LIMIT = 1.0  # seconds between allowed requests per user


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._last_call: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is not None:
            now = time.monotonic()
            last = self._last_call.get(user.id, 0.0)
            if now - last < _RATE_LIMIT:
                log.info("throttled", user_id=user.id)
                return None
            self._last_call[user.id] = now
        return await handler(event, data)
