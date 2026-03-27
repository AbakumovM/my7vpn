import structlog
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.apps.device.application.interactor import DeviceInteractor
from src.apps.device.application.interfaces.view import DeviceDetailInfo, DeviceSummary, DeviceView
from src.apps.device.domain.commands import CreateDevice, DeleteDevice, RenewSubscription
from src.apps.device.domain.exceptions import DeviceNotFound, SubscriptionNotFound
from src.infrastructure.auth import CurrentUser

router = APIRouter(prefix="/api/v1/devices", tags=["devices"], route_class=DishkaRoute)
log = structlog.get_logger(__name__)


class CreateDeviceRequest(BaseModel):
    device_type: str
    period_months: int
    amount: int


class RenewRequest(BaseModel):
    period_months: int
    amount: int


@router.get("/")
async def list_devices(
    telegram_id: CurrentUser,
    device_view: FromDishka[DeviceView],
) -> list[dict]:
    devices = await device_view.list_for_user(telegram_id)
    return [{"id": d.id, "device_name": d.device_name} for d in devices]


@router.get("/{device_id}")
async def get_device(
    device_id: int,
    device_view: FromDishka[DeviceView],
) -> dict:
    info = await device_view.get_full_info(device_id)
    if info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return {
        "device_name": info.device_name,
        "end_date": info.end_date,
        "amount": info.amount,
        "payment_date": info.payment_date,
    }


@router.post("/")
async def create_device(
    body: CreateDeviceRequest,
    telegram_id: CurrentUser,
    interactor: FromDishka[DeviceInteractor],
) -> dict:
    result = await interactor.create_device(
        CreateDevice(
            telegram_id=telegram_id,
            device_type=body.device_type,
            period_months=body.period_months,
            amount=body.amount,
        )
    )
    log.info(
        "device_created",
        device_name=result.device_name,
        device_type=body.device_type,
        period_months=body.period_months,
        amount=body.amount,
    )
    return {"device_name": result.device_name}


@router.delete("/{device_id}")
async def delete_device(
    device_id: int,
    interactor: FromDishka[DeviceInteractor],
) -> dict:
    try:
        name = await interactor.delete_device(DeleteDevice(device_id=device_id))
        log.info("device_deleted", device_id=device_id, device_name=name)
        return {"deleted": name}
    except DeviceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")


@router.post("/{device_name}/renew")
async def renew_subscription(
    device_name: str,
    body: RenewRequest,
    interactor: FromDishka[DeviceInteractor],
) -> dict:
    try:
        result = await interactor.renew_subscription(
            RenewSubscription(
                device_name=device_name,
                period_months=body.period_months,
                amount=body.amount,
            )
        )
        log.info(
            "subscription_renewed",
            device_name=result.device_name,
            period_months=body.period_months,
            amount=body.amount,
        )
        return {
            "device_name": result.device_name,
            "end_date": result.end_date.isoformat(),
            "plan": result.plan,
        }
    except DeviceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    except SubscriptionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
