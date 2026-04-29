from datetime import UTC, datetime

import pytest

from src.apps.user.application.interfaces.admin_view import (
    AdminChurn,
    AdminExpiring,
    AdminStats,
    AdminUserInfo,
)


def test_admin_stats_frozen():
    stats = AdminStats(
        total_users=100,
        active_subscribers=60,
        new_today=3,
        new_week=15,
        new_month=40,
    )
    assert stats.total_users == 100
    assert stats.active_subscribers == 60
    assert stats.new_today == 3
    with pytest.raises(Exception):
        stats.total_users = 999  # type: ignore


def test_admin_expiring_frozen():
    exp = AdminExpiring(expiring_3d=2, expiring_7d=8, expiring_30d=25)
    assert exp.expiring_3d == 2
    assert exp.expiring_7d == 8
    assert exp.expiring_30d == 25


def test_admin_churn_renewal_rate_bounds():
    churn = AdminChurn(churned_7d=2, churned_30d=5, renewal_rate_30d=75)
    assert 0 <= churn.renewal_rate_30d <= 100


def test_admin_churn_zero_expired():
    churn = AdminChurn(churned_7d=0, churned_30d=0, renewal_rate_30d=0)
    assert churn.renewal_rate_30d == 0


def test_admin_user_info_no_subscription():
    info = AdminUserInfo(
        telegram_id=123456,
        balance=50,
        referred_by=None,
        active_until=None,
        device_limit=None,
    )
    assert info.active_until is None
    assert info.referred_by is None


def test_admin_user_info_with_subscription():
    end = datetime(2026, 6, 1, tzinfo=UTC)
    info = AdminUserInfo(
        telegram_id=999,
        balance=200,
        referred_by=12345,
        active_until=end,
        device_limit=2,
    )
    assert info.active_until == end
    assert info.device_limit == 2
    assert info.referred_by == 12345
