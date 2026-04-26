# src/apps/device/application/interfaces/notification_view.py
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class ExpiringUserSubscriptionInfo:
    user_id: int
    telegram_id: int
    end_date: date
    days_before: int  # 7, 3, 1, 0


class NotificationView(Protocol):
    async def get_subscriptions_to_notify(
        self, days_offsets: list[int]
    ) -> list[ExpiringUserSubscriptionInfo]: ...
