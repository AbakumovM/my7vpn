from typing import Protocol

from src.apps.device.domain.models import UserPayment, UserSubscription


class SubscriptionGateway(Protocol):
    async def get_active_by_telegram_id(self, telegram_id: int) -> UserSubscription | None: ...

    async def save(self, sub: UserSubscription) -> UserSubscription: ...

    async def save_payment(self, payment: UserPayment) -> UserPayment: ...

    async def count_payments_for_user(self, telegram_id: int) -> int:
        """Count paid (amount > 0) UserPayment records for the user."""
        ...
