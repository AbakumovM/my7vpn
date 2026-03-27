from typing import Annotated

from fastapi import Header, HTTPException, status


async def get_current_user_id(
    x_telegram_id: Annotated[int | None, Header(alias="X-Telegram-Id")] = None,
) -> int:
    """
    Заглушка авторизации: читает telegram_id из заголовка X-Telegram-Id.
    Позже заменяется на Telegram Login Widget + JWT без изменения бизнес-логики.
    """
    if x_telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Telegram-Id header is required",
        )
    return x_telegram_id


from fastapi import Depends  # noqa: E402

CurrentUser = Annotated[int, Depends(get_current_user_id)]
