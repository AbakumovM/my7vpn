import hashlib
from urllib.parse import urlencode

from src.infrastructure.config import YuMoneySettings


def build_quickpay_url(settings: YuMoneySettings, amount: int, pending_id: int) -> str:
    """
    Строит URL ЮMoney Quickpay с pending_id как label.
    Документация: https://yoomoney.ru/docs/payment-buttons/using-api/forms
    """
    params = {
        "receiver": settings.wallet,
        "quickpay-form": "shop",
        "targets": f"VPN подписка #{pending_id}",
        "paymentType": "AC",
        "sum": str(amount),
        "label": str(pending_id),
    }
    if settings.success_url:
        params["successURL"] = settings.success_url
    return "https://yoomoney.ru/quickpay/confirm.xml?" + urlencode(params)


def verify_notification_signature(
    notification_secret: str,
    notification_type: str,
    operation_id: str,
    amount: str,
    currency: str,
    dt: str,        # поле "datetime" из уведомления ЮMoney — переименовано чтобы не shadowing builtin
    sender: str,
    codepro: str,   # приходит как строка "false" / "true"
    label: str,
    received_hash: str,
) -> bool:
    """
    Проверяет sha1_hash из HTTP-уведомления ЮMoney.
    Порядок полей строго фиксирован: notification_type & operation_id & amount &
    currency & datetime & sender & codepro & notification_secret & label
    """
    raw = "&".join([
        notification_type, operation_id, amount, currency,
        dt, sender, codepro, notification_secret, label,
    ])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest() == received_hash
