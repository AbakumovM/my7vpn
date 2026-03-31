from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, EmailStr

from src.apps.auth.application.interactor import AuthInteractor
from src.apps.auth.domain.commands import RequestOtp, VerifyBotToken, VerifyOtp
from src.apps.auth.domain.exceptions import (
    BotTokenExpired,
    BotTokenInvalid,
    OtpExpired,
    OtpInvalid,
)
from src.infrastructure.auth import CurrentUser
from src.infrastructure.config import app_config

router = APIRouter(prefix="/api/v1/auth", tags=["auth"], route_class=DishkaRoute)


class OtpRequestBody(BaseModel):
    email: EmailStr


class OtpVerifyBody(BaseModel):
    email: EmailStr
    code: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: int


class MeResponse(BaseModel):
    user_id: int


@router.post("/otp/request", status_code=status.HTTP_200_OK)
async def request_otp(
    body: OtpRequestBody,
    auth_interactor: FromDishka[AuthInteractor],
) -> dict[str, str]:
    await auth_interactor.request_otp(RequestOtp(email=body.email))
    return {"detail": "OTP sent to email"}


@router.post("/otp/verify")
async def verify_otp(
    body: OtpVerifyBody,
    response: Response,
    auth_interactor: FromDishka[AuthInteractor],
) -> AuthResponse:
    try:
        result = await auth_interactor.verify_otp(VerifyOtp(email=body.email, code=body.code))
    except OtpInvalid as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code",
        ) from exc
    except OtpExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP code expired",
        ) from exc

    response.set_cookie(
        key="access_token",
        value=result.access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=app_config.auth.jwt_expire_minutes * 60,
    )
    return AuthResponse(access_token=result.access_token, user_id=result.user_id)


@router.get("/bot-token/{token}")
async def verify_bot_token(
    token: str,
    response: Response,
    auth_interactor: FromDishka[AuthInteractor],
) -> AuthResponse:
    try:
        result = await auth_interactor.verify_bot_token(VerifyBotToken(token=token))
    except BotTokenInvalid as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token",
        ) from exc
    except BotTokenExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token expired",
        ) from exc

    response.set_cookie(
        key="access_token",
        value=result.access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=app_config.auth.jwt_expire_minutes * 60,
    )
    return AuthResponse(access_token=result.access_token, user_id=result.user_id)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(key="access_token")
    return {"detail": "Logged out"}


@router.get("/me")
async def me(user_id: CurrentUser) -> MeResponse:
    return MeResponse(user_id=user_id)
