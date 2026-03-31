from dataclasses import dataclass


@dataclass(frozen=True)
class RequestOtp:
    email: str


@dataclass(frozen=True)
class VerifyOtp:
    email: str
    code: str


@dataclass(frozen=True)
class CreateBotToken:
    user_id: int


@dataclass(frozen=True)
class VerifyBotToken:
    token: str
