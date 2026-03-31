class OtpExpired(Exception):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"OTP expired for {email}")


class OtpInvalid(Exception):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"Invalid OTP for {email}")


class BotTokenExpired(Exception):
    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__("Bot auth token expired")


class BotTokenInvalid(Exception):
    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__("Invalid bot auth token")
