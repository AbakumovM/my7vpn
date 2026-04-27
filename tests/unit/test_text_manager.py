from datetime import date

from src.common.bot.lexicon.text_manager import TextManager


def test_expiry_notice_7_days() -> None:
    text = TextManager.subscription_expiry_notice(days_before=7, end_date=date(2026, 5, 1))
    assert "7 дней" in text
    assert "01.05.2026" in text


def test_expiry_notice_3_days() -> None:
    text = TextManager.subscription_expiry_notice(days_before=3, end_date=date(2026, 5, 1))
    assert "3 дня" in text
    assert "01.05.2026" in text


def test_expiry_notice_1_day() -> None:
    text = TextManager.subscription_expiry_notice(days_before=1, end_date=date(2026, 5, 1))
    assert "Завтра" in text
    assert "01.05.2026" in text


def test_expiry_notice_0_days() -> None:
    text = TextManager.subscription_expiry_notice(days_before=0, end_date=date(2026, 5, 1))
    assert "Сегодня" in text
    # Дата в тексте не нужна — подписка истекает сегодня
