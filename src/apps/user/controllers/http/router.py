from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, status

from src.apps.user.application.interactor import UserInteractor
from src.apps.user.application.interfaces.view import UserView
from src.apps.user.domain.commands import GetOrCreateUser, GetReferralCode
from src.infrastructure.auth import CurrentUser

router = APIRouter(prefix="/api/v1/users", tags=["users"], route_class=DishkaRoute)


@router.get("/me")
async def get_me(
    user_id: CurrentUser,
    user_view: FromDishka[UserView],
    interactor: FromDishka[UserInteractor],
) -> dict:
    telegram_id = await user_view.get_telegram_id(user_id)
    if telegram_id is None:
        # Пользователь с сайта (без Telegram) — возвращаем данные по user_id
        return {
            "user_id": user_id,
            "telegram_id": None,
            "balance": 0,
            "free_months": False,
            "referral_code": None,
        }
    user = await interactor.get_or_create(GetOrCreateUser(telegram_id=telegram_id))
    return {
        "user_id": user_id,
        "telegram_id": user.telegram_id,
        "email": user.email,
        "balance": user.balance,
        "free_months": user.free_months,
        "referral_code": user.referral_code,
    }


@router.get("/referral")
async def get_referral(
    user_id: CurrentUser,
    user_view: FromDishka[UserView],
    interactor: FromDishka[UserInteractor],
) -> dict:
    telegram_id = await user_view.get_telegram_id(user_id)
    if telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Referral system requires Telegram account",
        )
    result = await interactor.get_referral_code(GetReferralCode(telegram_id=telegram_id))
    device_count = await user_view.get_device_count(telegram_id)
    return {
        "referral_code": result.referral_code,
        "referral_link": f"https://t.me/my7vpnbot?start={result.referral_code}",
        "invited_count": device_count,
    }
