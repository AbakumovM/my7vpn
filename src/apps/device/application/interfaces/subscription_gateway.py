from typing import Protocol

from src.apps.device.domain.models import UserPayment, UserSubscription


class SubscriptionGateway(Protocol):
    async def get_active_by_telegram_id(self, telegram_id: int) -> UserSubscription | None:
        """Legacy lookup for bot/migration flows where telegram_id is available."""
        ...

    async def get_active_by_user_id(self, user_id: int) -> UserSubscription | None:
        """Primary lookup by users.id — works for all user types."""
        ...

    async def save(self, sub: UserSubscription) -> UserSubscription: ...

    async def save_payment(self, payment: UserPayment) -> UserPayment: ...

    async def count_payments_for_user(self, user_id: int) -> int:
        """Count paid (amount > 0) UserPayment records for the user by user_id."""
        ...
