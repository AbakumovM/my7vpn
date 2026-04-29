from datetime import UTC, datetime

import structlog
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, status

from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.user.adapters.gateway import SQLAlchemyUserGateway

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/cabinet", tags=["cabinet"], route_class=DishkaRoute)


async def _get_user_or_404(web_key: str, user_gateway: SQLAlchemyUserGateway):
    user = await user_gateway.get_by_web_key(web_key)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cabinet not found")
    return user


@router.get("/{web_key}")
async def get_cabinet(
    web_key: str,
    user_gateway: FromDishka[SQLAlchemyUserGateway],
    device_view: FromDishka[DeviceView],
    remnawave_gateway: FromDishka[RemnawaveGateway],
) -> dict:
    user = await _get_user_or_404(web_key, user_gateway)

    subscription = None
    if user.telegram_id is not None:
        sub = await device_view.get_subscription_info(user.telegram_id)
        if sub is not None and sub.end_date is not None:
            days_left = (sub.end_date - datetime.now(UTC)).days
            subscription = {
                "is_active": days_left > 0,
                "end_date": sub.end_date.isoformat(),
                "days_left": max(days_left, 0),
                "device_limit": sub.device_limit,
                "subscription_url": sub.subscription_url,
            }

    hwid_devices = []
    if user.remnawave_uuid is not None:
        try:
            devices = await remnawave_gateway.get_hwid_devices(user.remnawave_uuid)
            hwid_devices = [
                {
                    "hwid": d.hwid,
                    "platform": d.platform,
                    "os_version": d.os_version,
                    "device_model": d.device_model,
                }
                for d in devices
            ]
        except Exception:
            log.warning("cabinet_hwid_fetch_failed", web_key=web_key)

    return {
        "user": {
            "balance": user.balance,
            "referral_code": user.referral_code,
        },
        "subscription": subscription,
        "hwid_devices": hwid_devices,
    }


@router.delete("/{web_key}/hwid/{hwid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hwid_device(
    web_key: str,
    hwid: str,
    user_gateway: FromDishka[SQLAlchemyUserGateway],
    remnawave_gateway: FromDishka[RemnawaveGateway],
) -> None:
    user = await _get_user_or_404(web_key, user_gateway)
    if user.remnawave_uuid is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Remnawave account")
    try:
        await remnawave_gateway.delete_hwid_device(user.remnawave_uuid, hwid)
    except Exception as exc:
        log.warning("cabinet_hwid_delete_failed", web_key=web_key, hwid=hwid)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Remnawave error") from exc


@router.delete("/{web_key}/hwid", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_hwid_devices(
    web_key: str,
    user_gateway: FromDishka[SQLAlchemyUserGateway],
    remnawave_gateway: FromDishka[RemnawaveGateway],
) -> None:
    user = await _get_user_or_404(web_key, user_gateway)
    if user.remnawave_uuid is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Remnawave account")
    try:
        await remnawave_gateway.delete_all_hwid_devices(user.remnawave_uuid)
    except Exception as exc:
        log.warning("cabinet_hwid_delete_all_failed", web_key=web_key)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Remnawave error") from exc
