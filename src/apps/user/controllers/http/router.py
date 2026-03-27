from dataclasses import asdict

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter

from src.apps.user.application.interactor import UserInteractor, UserInfo, ReferralCodeInfo
from src.apps.user.application.interfaces.view import UserView
from src.apps.user.domain.commands import GetOrCreateUser, GetReferralCode
from src.infrastructure.auth import CurrentUser

router = APIRouter(prefix="/api/v1/users", tags=["users"], route_class=DishkaRoute)


@router.get("/me")
async def get_me(
    telegram_id: CurrentUser,
    interactor: FromDishka[UserInteractor],
) -> dict:
    user = await interactor.get_or_create(GetOrCreateUser(telegram_id=telegram_id))
    return {
        "telegram_id": user.telegram_id,
        "balance": user.balance,
        "free_months": user.free_months,
        "referral_code": user.referral_code,
    }


@router.get("/referral")
async def get_referral(
    telegram_id: CurrentUser,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
) -> dict:
    result = await interactor.get_referral_code(GetReferralCode(telegram_id=telegram_id))
    device_count = await user_view.get_device_count(telegram_id)
    return {
        "referral_code": result.referral_code,
        "referral_link": f"https://t.me/my7vpnbot?start={result.referral_code}",
        "invited_count": device_count,  # placeholder
    }
