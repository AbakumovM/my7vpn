from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class UserForMigrationInfo:
    user_id: int
    telegram_id: int
    end_date: datetime


class MigrationView(Protocol):
    async def get_users_for_migration(self) -> list[UserForMigrationInfo]: ...
