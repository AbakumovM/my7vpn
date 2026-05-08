import structlog
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from src.apps.device.application.interactor import ConfirmPaymentResult, DeviceInteractor
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.device.domain.commands import ConfirmPayment, CreatePendingPayment
from src.apps.device.domain.exceptions import PendingPaymentNotFound
from src.apps.user.application.interfaces.view import UserView
from src.common.bot.keyboards.user_actions import TARIFF_MATRIX
from src.infrastructure.auth import CurrentUser
from src.infrastructure.config import app_config

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/payments", tags=["payments"], route_class=DishkaRoute)

_VALID_PLANS = {1, 3, 6, 12}
_VALID_DEVICE_LIMITS = {1, 2, 3}


class InitiatePaymentRequest(BaseModel):
    action: str
    plan: int
    device_limit: int

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("new", "renew"):
            raise ValueError("action must be 'new' or 'renew'")
        return v

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: int) -> int:
        if v not in _VALID_PLANS:
            raise ValueError(f"plan must be one of {sorted(_VALID_PLANS)}")
        return v

    @field_validator("device_limit")
    @classmethod
    def validate_device_limit(cls, v: int) -> int:
        if v not in _VALID_DEVICE_LIMITS:
            raise ValueError(f"device_limit must be one of {sorted(_VALID_DEVICE_LIMITS)}")
        return v


@router.post("/initiate")
async def initiate_payment(
    body: InitiatePaymentRequest,
    user_id: CurrentUser,
    user_view: FromDishka[UserView],
    interactor: FromDishka[DeviceInteractor],
) -> dict:
    full_amount: int = TARIFF_MATRIX[body.device_limit][body.plan]
    balance: int = await user_view.get_balance_by_user_id(user_id)
    balance_used: int = min(balance, full_amount)
    final_amount: int = full_amount - balance_used

    pending = await interactor.create_pending_payment(
        CreatePendingPayment(
            user_id=user_id,
            action=body.action,
            device_type="vpn",
            duration=body.plan,
            amount=final_amount,
            balance_to_deduct=balance_used,
            device_limit=body.device_limit,
        )
    )

    payment_url: str | None = None
    if final_amount > 0:
        if not app_config.yookassa.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service unavailable",
            )
        from src.infrastructure.yookassa.client import YooKassaClient
        yookassa_client = YooKassaClient(app_config.yookassa)
        created = await yookassa_client.create_payment(
            amount=final_amount, pending_id=pending.id
        )
        payment_url = created.confirmation_url

    log.info(
        "payment_initiated",
        user_id=user_id,
        pending_id=pending.id,
        action=body.action,
        plan=body.plan,
        full_amount=full_amount,
        balance_used=balance_used,
        final_amount=final_amount,
    )
    return {
        "pending_id": pending.id,
        "amount": full_amount,
        "balance_used": balance_used,
        "final_amount": final_amount,
        "payment_url": payment_url,
    }


@router.post("/{pending_id}/confirm")
async def confirm_payment_endpoint(
    pending_id: int,
    user_id: CurrentUser,
    device_view: FromDishka[DeviceView],
    interactor: FromDishka[DeviceInteractor],
) -> dict:
    pending_status = await device_view.get_pending_status(pending_id, user_id)
    if pending_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    if pending_status.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment already {pending_status.status}",
        )

    try:
        result: ConfirmPaymentResult = await interactor.confirm_payment(
            ConfirmPayment(pending_id=pending_id)
        )
    except PendingPaymentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        ) from exc

    log.info("payment_confirmed_via_api", user_id=user_id, pending_id=pending_id)
    return {
        "subscription_url": result.subscription_url,
        "end_date": result.end_date.isoformat(),
    }


@router.get("/history")
async def get_payment_history(
    user_id: CurrentUser,
    device_view: FromDishka[DeviceView],
) -> list[dict]:
    items = await device_view.get_payment_history(user_id)
    return [
        {
            "id": item.id,
            "amount": item.amount,
            "date": item.date.isoformat(),
            "plan": item.plan,
            "device_limit": item.device_limit,
            "payment_method": item.payment_method,
            "status": item.status,
        }
        for item in items
    ]


@router.get("/{pending_id}/status")
async def get_payment_status(
    pending_id: int,
    user_id: CurrentUser,
    device_view: FromDishka[DeviceView],
) -> dict:
    result = await device_view.get_pending_status(pending_id, user_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return {
        "status": result.status,
        "subscription_url": result.subscription_url,
        "end_date": result.end_date.isoformat() if result.end_date else None,
    }
