# src/common/scheduler/tasks.py
from datetime import UTC, datetime
from io import StringIO

import structlog
from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from dishka import AsyncContainer

from src.apps.device.application.interfaces.notification_gateway import NotificationLogGateway
from src.apps.device.application.interfaces.notification_view import NotificationView
from src.common.bot.cbdata import VpnCallback
from src.common.bot.keyboards.user_actions import VpnAction
from src.common.bot.lexicon.text_manager import TextManager
from src.infrastructure.config import app_config

ADMIN_ID = app_config.bot.admin_id
log = structlog.get_logger(__name__)

NOTIFICATION_DAYS = [7, 3, 1, 0]


def _renew_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Продлить подписку",
                    callback_data=VpnCallback(action=VpnAction.RENEW).pack(),
                )
            ]
        ]
    )


async def send_expiry_notifications(bot: Bot, container: AsyncContainer) -> None:
    log.info("notification_job_started")
    sent = 0
    skipped = 0
    errors = 0

    async with container() as request_container:
        view = await request_container.get(NotificationView)
        gateway = await request_container.get(NotificationLogGateway)
        subscriptions = await view.get_subscriptions_to_notify(NOTIFICATION_DAYS)
        for sub in subscriptions:
            if await gateway.is_sent(
                user_id=sub.user_id,
                days_before=sub.days_before,
                sub_end_date=sub.end_date,
            ):
                skipped += 1
                continue
            try:
                text = TextManager.subscription_expiry_notice(sub.days_before, sub.end_date)
                await bot.send_message(
                    chat_id=sub.telegram_id,
                    text=text,
                    reply_markup=_renew_keyboard(),
                )
                await gateway.mark_sent(
                    user_id=sub.user_id,
                    days_before=sub.days_before,
                    sub_end_date=sub.end_date,
                )
                log.info(
                    "notification_sent",
                    telegram_id=sub.telegram_id,
                    days_before=sub.days_before,
                    end_date=str(sub.end_date),
                )
                sent += 1
            except Exception:
                log.exception(
                    "notification_send_failed",
                    telegram_id=sub.telegram_id,
                    days_before=sub.days_before,
                )
                errors += 1

    log.info("notification_job_done", sent=sent, skipped=skipped, errors=errors)
    await send_admin_report(bot, sent, skipped, errors)


async def send_admin_report(bot: Bot, sent: int, skipped: int, errors: int) -> None:
    report = (
        f"🔔 Уведомления {datetime.now(UTC).strftime('%d.%m.%Y %H:%M')}\n"
        f"📬 Отправлено: {sent}\n"
        f"⏭ Пропущено (уже отправлено): {skipped}\n"
        f"❌ Ошибок: {errors}"
    )
    try:
        await send_long_message(bot, ADMIN_ID, report)
    except Exception:
        log.exception("notification_admin_report_failed")


async def send_long_message(bot: Bot, chat_id: int, text: str, max_len: int = 4000) -> None:
    if len(text) <= max_len:
        await bot.send_message(chat_id=chat_id, text=text)
    else:
        buffer = StringIO()
        buffer.write(text)
        buffer.seek(0)
        input_file = BufferedInputFile(buffer.getvalue().encode("utf-8"), filename="report.txt")
        await bot.send_document(chat_id=chat_id, document=input_file)
