import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

log = structlog.get_logger(__name__)

_RATE_LIMIT = 1.0   # seconds between allowed requests per user
_TTL = 300.0        # entries older than this are pruned
_PRUNE_EVERY = 500  # prune every N processed requests


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._last_call: dict[int, float] = {}
        self._call_count = 0

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

            self._call_count += 1
            if self._call_count >= _PRUNE_EVERY:
                self._call_count = 0
                cutoff = now - _TTL
                self._last_call = {
                    uid: t for uid, t in self._last_call.items() if t > cutoff
                }

        return await handler(event, data)
