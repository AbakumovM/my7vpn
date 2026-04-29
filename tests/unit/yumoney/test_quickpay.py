from src.infrastructure.config import YuMoneySettings
from src.infrastructure.yumoney.quickpay import build_quickpay_url, verify_notification_signature


def test_build_quickpay_url_contains_required_params():
    settings = YuMoneySettings(wallet="4100112345678", notification_secret="secret", enabled=True)
    url = build_quickpay_url(settings=settings, amount=150, pending_id=42)
    assert "receiver=4100112345678" in url
    assert "sum=150" in url
    assert "label=42" in url
    assert "quickpay-form=shop" in url
    assert url.startswith("https://yoomoney.ru/quickpay/confirm.xml")


def test_build_quickpay_url_includes_success_url_when_set():
    settings = YuMoneySettings(wallet="4100112345678", success_url="https://example.com/ok")
    url = build_quickpay_url(settings=settings, amount=100, pending_id=1)
    assert "successURL=" in url


def test_build_quickpay_url_no_success_url_when_empty():
    settings = YuMoneySettings(wallet="4100112345678", success_url="")
    url = build_quickpay_url(settings=settings, amount=100, pending_id=1)
    assert "successURL" not in url


def test_verify_notification_signature_valid():
    # Строим ожидаемый hash вручную
    import hashlib
    fields = ["card-incoming", "op-123", "150.00", "643", "2024-01-01T12:00:00Z", "sender-wallet", "false", "mysecret", "42"]
    expected = hashlib.sha1("&".join(fields).encode()).hexdigest()

    result = verify_notification_signature(
        notification_secret="mysecret",
        notification_type="card-incoming",
        operation_id="op-123",
        amount="150.00",
        currency="643",
        dt="2024-01-01T12:00:00Z",
        sender="sender-wallet",
        codepro="false",
        label="42",
        received_hash=expected,
    )
    assert result is True


def test_verify_notification_signature_invalid():
    result = verify_notification_signature(
        notification_secret="mysecret",
        notification_type="card-incoming",
        operation_id="op-123",
        amount="150.00",
        currency="643",
        dt="2024-01-01T12:00:00Z",
        sender="sender-wallet",
        codepro="false",
        label="42",
        received_hash="wronghash",
    )
    assert result is False


def test_verify_signature_codepro_is_string():
    """codepro приходит как строка 'false', не булев False — проверяем что это учтено."""
    import hashlib
    # С "false" строкой
    fields = ["notification", "op", "100.00", "643", "dt", "", "false", "secret", "1"]
    expected = hashlib.sha1("&".join(fields).encode()).hexdigest()

    assert verify_notification_signature(
        notification_secret="secret",
        notification_type="notification",
        operation_id="op",
        amount="100.00",
        currency="643",
        dt="dt",
        sender="",
        codepro="false",
        label="1",
        received_hash=expected,
    ) is True
