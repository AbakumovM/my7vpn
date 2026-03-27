from typing import Protocol

from src.apps.user.domain.models import User


class UserGateway(Protocol):
    async def get_by_telegram_id(self, telegram_id: int) -> User | None: ...

    async def get_by_referral_code(self, referral_code: str) -> User | None: ...

    async def save(self, user: User) -> None: ...
