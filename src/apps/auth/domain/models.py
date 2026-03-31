from dataclasses import dataclass
from datetime import datetime


@dataclass
class OtpCode:
    email: str
    code: str
    created_at: datetime
    expires_at: datetime
    is_used: bool = False
    id: int | None = None


@dataclass
class BotAuthToken:
    user_id: int
    token: str
    created_at: datetime
    expires_at: datetime
    is_used: bool = False
    id: int | None = None
