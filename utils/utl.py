import hashlib


def generate_referral_code(telegram_id: int) -> str:
    return hashlib.md5(str(telegram_id).encode()).hexdigest()
