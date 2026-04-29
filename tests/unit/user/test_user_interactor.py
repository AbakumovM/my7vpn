import pytest
from unittest.mock import AsyncMock

from src.apps.user.application.interactor import UserInteractor
from src.apps.user.domain.commands import (
    AddReferralBonus,
    DeductUserBalance,
    GetOrCreateUser,
    GetReferralCode,
    MarkFreeMonthUsed,
)
from src.apps.user.domain.exceptions import (
    InsufficientBalance,
    ReferralNotFound,
    UserNotFound,
)
from src.apps.user.domain.models import User


pytestmark = pytest.mark.asyncio


class TestGetOrCreate:
    async def test_creates_new_user(
        self, interactor: UserInteractor, mock_gateway: AsyncMock, mock_uow: AsyncMock
    ) -> None:
        mock_gateway.get_by_telegram_id.return_value = None

        result = await interactor.get_or_create(GetOrCreateUser(telegram_id=111))

        mock_gateway.save.assert_called_once()
        mock_uow.commit.assert_called_once()
        assert result.telegram_id == 111
        assert result.balance == 0
        assert result.free_months is False

    async def test_returns_existing_user(
        self, interactor: UserInteractor, mock_gateway: AsyncMock, mock_uow: AsyncMock
    ) -> None:
        existing = User(telegram_id=222, balance=100, free_months=True)
        mock_gateway.get_by_telegram_id.return_value = existing

        result = await interactor.get_or_create(GetOrCreateUser(telegram_id=222))

        mock_gateway.save.assert_not_called()
        mock_uow.commit.assert_not_called()
        assert result.balance == 100
        assert result.free_months is True

    async def test_resolves_referral_code(
        self, interactor: UserInteractor, mock_gateway: AsyncMock, mock_uow: AsyncMock
    ) -> None:
        referrer = User(telegram_id=999, balance=0)
        mock_gateway.get_by_telegram_id.return_value = None
        mock_gateway.get_by_referral_code.return_value = referrer

        result = await interactor.get_or_create(
            GetOrCreateUser(telegram_id=111, referred_by_code="abc123")
        )

        saved_user: User = mock_gateway.save.call_args[0][0]
        assert saved_user.referred_by == 999

    async def test_raises_on_invalid_referral(
        self, interactor: UserInteractor, mock_gateway: AsyncMock
    ) -> None:
        mock_gateway.get_by_telegram_id.return_value = None
        mock_gateway.get_by_referral_code.return_value = None

        with pytest.raises(ReferralNotFound):
            await interactor.get_or_create(
                GetOrCreateUser(telegram_id=111, referred_by_code="invalid")
            )


class TestGetReferralCode:
    async def test_generates_code_if_missing(
        self, interactor: UserInteractor, mock_gateway: AsyncMock, mock_uow: AsyncMock
    ) -> None:
        user = User(telegram_id=333, referral_code=None)
        mock_gateway.get_by_telegram_id.return_value = user

        result = await interactor.get_referral_code(GetReferralCode(telegram_id=333))

        assert result.referral_code is not None
        assert len(result.referral_code) == 8
        mock_gateway.save.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_returns_existing_code(
        self, interactor: UserInteractor, mock_gateway: AsyncMock, mock_uow: AsyncMock
    ) -> None:
        user = User(telegram_id=444, referral_code="existing")
        mock_gateway.get_by_telegram_id.return_value = user

        result = await interactor.get_referral_code(GetReferralCode(telegram_id=444))

        assert result.referral_code == "existing"
        mock_gateway.save.assert_not_called()

    async def test_raises_if_user_not_found(
        self, interactor: UserInteractor, mock_gateway: AsyncMock
    ) -> None:
        mock_gateway.get_by_telegram_id.return_value = None

        with pytest.raises(UserNotFound):
            await interactor.get_referral_code(GetReferralCode(telegram_id=999))


class TestAddReferralBonus:
    async def test_adds_bonus_correctly(
        self, interactor: UserInteractor, mock_gateway: AsyncMock, mock_uow: AsyncMock
    ) -> None:
        user = User(telegram_id=555, balance=50)
        mock_gateway.get_by_telegram_id.return_value = user

        result = await interactor.add_referral_bonus(
            AddReferralBonus(referrer_telegram_id=555, amount=50)
        )

        # Проверяем: баланс увеличился, не перезаписан
        assert result.balance == 100

    async def test_raises_if_user_not_found(
        self, interactor: UserInteractor, mock_gateway: AsyncMock
    ) -> None:
        mock_gateway.get_by_telegram_id.return_value = None

        with pytest.raises(UserNotFound):
            await interactor.add_referral_bonus(
                AddReferralBonus(referrer_telegram_id=999)
            )


class TestDeductBalance:
    async def test_deducts_correctly(
        self, interactor: UserInteractor, mock_gateway: AsyncMock, mock_uow: AsyncMock
    ) -> None:
        user = User(telegram_id=666, balance=300)
        mock_gateway.get_by_telegram_id.return_value = user

        result = await interactor.deduct_balance(
            DeductUserBalance(telegram_id=666, amount=150)
        )

        # Проверяем: 300 - 150 = 150 (исправление бага: -= вместо =)
        assert result.balance == 150

    async def test_raises_on_insufficient_balance(
        self, interactor: UserInteractor, mock_gateway: AsyncMock
    ) -> None:
        user = User(telegram_id=777, balance=50)
        mock_gateway.get_by_telegram_id.return_value = user

        with pytest.raises(InsufficientBalance):
            await interactor.deduct_balance(
                DeductUserBalance(telegram_id=777, amount=150)
            )

    async def test_raises_if_user_not_found(
        self, interactor: UserInteractor, mock_gateway: AsyncMock
    ) -> None:
        mock_gateway.get_by_telegram_id.return_value = None

        with pytest.raises(UserNotFound):
            await interactor.deduct_balance(
                DeductUserBalance(telegram_id=999, amount=100)
            )


class TestMarkFreeMonthUsed:
    async def test_sets_free_months_true(
        self, interactor: UserInteractor, mock_gateway: AsyncMock, mock_uow: AsyncMock
    ) -> None:
        user = User(telegram_id=888, free_months=False)
        mock_gateway.get_by_telegram_id.return_value = user

        result = await interactor.mark_free_month_used(
            MarkFreeMonthUsed(telegram_id=888)
        )

        assert result.free_months is True
        mock_gateway.save.assert_called_once()
        mock_uow.commit.assert_called_once()
