from typing import Any

import structlog
from aiogram import Bot
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.apps.device.application.interactor import ConfirmPaymentResult, DeviceInteractor
from src.apps.device.domain.commands import ConfirmPayment
from src.apps.device.domain.exceptions import PendingPaymentNotFound
from src.common.bot.keyboards.keyboards import get_keyboard_vpn_received, return_start
from src.infrastructure.config import app_config
from src.infrastructure.yookassa.client import YooKassaClient

log = structlog.get_logger(__name__)
router = APIRouter(
    prefix="/api/v1/payments/yookassa",
    tags=["payments"],
    route_class=DishkaRoute,
)


class YooKassaWebhook(BaseModel):
    event: str
    object: dict[str, Any]


@router.post("/webhook")
async def yookassa_webhook(
    body: YooKassaWebhook,
    request: Request,
    interactor: FromDishka[DeviceInteractor],
) -> JSONResponse:
    if body.event != "payment.succeeded":
        return JSONResponse(content={"status": "ignored"})

    payment_id: str = body.object.get("id", "")
    metadata: dict[str, Any] = body.object.get("metadata", {})
    pending_id_str: str = metadata.get("pending_id", "")

    if not pending_id_str.isdigit():
        log.warning("yookassa_webhook_no_pending_id", payment_id=payment_id)
        return JSONResponse(content={"status": "ignored"})

    pending_id = int(pending_id_str)

    # Верификация: перепроверяем статус через API ЮKassa
    yookassa_client = YooKassaClient(app_config.yookassa)
    try:
        status = await yookassa_client.get_payment_status(payment_id)
    except Exception:
        log.exception("yookassa_status_check_error", payment_id=payment_id)
        return JSONResponse(content={"status": "error"})

    if status != "succeeded":
        log.warning("yookassa_payment_not_succeeded", payment_id=payment_id, status=status)
        return JSONResponse(content={"status": "not_succeeded"})

    # Проверка суммы
    try:
        paid_str = body.object.get("amount", {}).get("value", "0")
        float(paid_str)
    except (ValueError, TypeError):
        log.warning("yookassa_invalid_amount", payment_id=payment_id)
        return JSONResponse(content={"status": "invalid_amount"})

    bot: Bot = request.app.state.bot

    # Подтверждаем платёж
    try:
        result = await interactor.confirm_payment(ConfirmPayment(pending_id=pending_id))
    except PendingPaymentNotFound:
        return JSONResponse(content={"status": "already_processed"})
    except Exception:
        log.exception("yookassa_confirm_error", pending_id=pending_id)
        return JSONResponse(content={"status": "error"})

    # Уведомляем пользователя
    await _notify_user(bot, result)

    if result.referrer_telegram_id is not None:
        try:
            await bot.send_message(
                chat_id=result.referrer_telegram_id,
                text="🎉 Ваш друг оформил подписку! Вам начислено 50 руб. на баланс.",
            )
        except Exception:
            log.warning("referral_bonus_notify_failed", referrer_id=result.referrer_telegram_id)

    # Уведомляем админа (информационно, без кнопок)
    end_str = result.end_date.strftime("%d.%m.%Y")
    action_label = "Новая подписка" if result.action == "new" else "Продление"
    details = (
        f"📱 Устройств: {result.device_limit} | 📅 {result.duration} мес | 💳 {result.amount}₽"
    )
    await bot.send_message(
        chat_id=app_config.bot.admin_id,
        text=(
            f"✅ ЮKassa автоплатёж\n"
            f"👤 {result.user_telegram_id}\n"
            f"{action_label} до {end_str}\n"
            f"{details}\n"
            f"payment_id: {payment_id}"
        ),
    )
    log.info("yookassa_confirmed", pending_id=pending_id, payment_id=payment_id)
    return JSONResponse(content={"status": "ok"})


async def _notify_user(bot: Bot, result: ConfirmPaymentResult) -> None:
    """Отправляет пользователю subscription_url или сообщение об активации."""
    if result.subscription_url:
        if result.action == "new":
            await bot.send_message(
                chat_id=result.user_telegram_id,
                text=(
                    "✅ Оплата прошла успешно!\n\n"
                    "Ваша ссылка для подключения — скопируйте и вставьте в приложение Happ:\n\n"
                    f"<code>{result.subscription_url}</code>"
                ),
                reply_markup=get_keyboard_vpn_received(),
            )
        else:
            end_str = result.end_date.strftime("%d.%m.%Y")
            await bot.send_message(
                chat_id=result.user_telegram_id,
                text=f"✅ Подписка продлена до {end_str}.",
                reply_markup=get_keyboard_vpn_received(),
            )
    else:
        end_str = result.end_date.strftime("%d.%m.%Y")
        await bot.send_message(
            chat_id=result.user_telegram_id,
            text=f"✅ Оплата подтверждена! Подписка активна до {end_str}.",
            reply_markup=return_start(),
        )
