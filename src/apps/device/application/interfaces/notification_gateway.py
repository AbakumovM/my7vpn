# src/apps/device/application/interfaces/notification_gateway.py
from datetime import date
from typing import Protocol


class NotificationLogGateway(Protocol):
    async def is_sent(
        self, user_id: int, days_before: int, sub_end_date: date
    ) -> bool: ...

    async def mark_sent(
        self, user_id: int, days_before: int, sub_end_date: date
    ) -> None: ...
