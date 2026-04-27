class UserNotFound(Exception):
    def __init__(self, telegram_id: int) -> None:
        super().__init__(f"User {telegram_id} not found")
        self.telegram_id = telegram_id


class ReferralNotFound(Exception):
    def __init__(self, referral_code: str) -> None:
        super().__init__(f"Referral code '{referral_code}' not found")
        self.referral_code = referral_code


class InsufficientBalance(Exception):
    def __init__(self, telegram_id: int, balance: int, required: int) -> None:
        super().__init__(f"User {telegram_id} has {balance}, required {required}")
        self.telegram_id = telegram_id
        self.balance = balance
        self.required = required
