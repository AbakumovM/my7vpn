from fastapi import APIRouter

from src.common.bot.keyboards.user_actions import TARIFF_MATRIX

router = APIRouter(prefix="/api/v1", tags=["tariffs"])


@router.get("/tariffs")
async def get_tariffs() -> dict:
    """Тарифная матрица: device_limit → plan_months → price_rub. Без авторизации."""
    return {
        str(device_limit): {
            str(months): price
            for months, price in plans.items()
        }
        for device_limit, plans in TARIFF_MATRIX.items()
    }
