from typing import Protocol


class EmailSender(Protocol):
    async def send_otp(self, email: str, code: str) -> None: ...
