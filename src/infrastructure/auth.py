from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status

from src.infrastructure.config import app_config

_cfg = app_config.auth


def create_jwt(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(minutes=_cfg.jwt_expire_minutes),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, _cfg.jwt_secret, algorithm=_cfg.jwt_algorithm)


def decode_jwt(token: str) -> int:
    try:
        payload = jwt.decode(token, _cfg.jwt_secret, algorithms=[_cfg.jwt_algorithm])
        return int(payload["sub"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user_id(
    request: Request,
    access_token: Annotated[str | None, Cookie()] = None,
) -> int:
    """Извлекает user_id из httpOnly cookie или заголовка Authorization."""
    token: str | None = access_token

    if token is None:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return decode_jwt(token)


CurrentUser = Annotated[int, Depends(get_current_user_id)]
