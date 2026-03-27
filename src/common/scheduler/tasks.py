import asyncio
from datetime import datetime
from io import StringIO

import structlog

from aiogram import Bot
from aiogram.types import BufferedInputFile
from dishka import AsyncContainer

from src.apps.device.application.interfaces.view import DeviceView
from src.common.bot.lexicon.text_manager import bot_repl
from src.infrastructure.config import app_config

ADMIN_ID = app_config.bot.admin_id
log = structlog.get_logger(__name__)


async def check_pending_subscriptions(bot: Bot, container: AsyncContainer) -> None:
    log.info("scheduler_subscription_check_started")
    async with container() as request_container:
        device_view = await request_container.get(DeviceView)
        pending = await device_view.get_expiring_today()

    log.info("scheduler_subscription_check_done", pending_count=len(pending))

    if pending:
        await asyncio.gather(
            *(send_message_end_payments(item, bot) for item in pending),
            return_exceptions=True,
        )

        report = f"🔔 Отчёт на {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        report += f"📬 Найдено {len(pending)} подписок, заканчивающихся сегодня:\n\n"
        for idx, p in enumerate(pending, 1):
            report += (
                f"{idx}. {p.device_name} (ID: {p.telegram_id})\n"
                f"📌 План: {p.plan}\n"
                f"📅 Начало: {p.start_date.strftime('%d.%m.%Y')}\n"
                f"🔚 Окончание: {p.end_date.strftime('%d.%m.%Y')}\n"
                f"---\n"
            )
    else:
        report = (
            f"🔔 Отчёт на {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"✅ Нет активных подписок, требующих уведомления."
        )

    try:
        await send_long_message(bot, ADMIN_ID, report)
    except Exception:
        log.exception("scheduler_admin_report_failed", admin_id=ADMIN_ID)


async def send_long_message(bot: Bot, chat_id: int, text: str, max_len: int = 4000) -> None:
    if len(text) <= max_len:
        await bot.send_message(chat_id=chat_id, text=text)
    else:
        buffer = StringIO()
        buffer.write(text)
        buffer.seek(0)
        input_file = BufferedInputFile(buffer.getvalue().encode("utf-8"), filename="report.txt")
        await bot.send_document(chat_id=chat_id, document=input_file)


async def send_message_end_payments(item: object, bot: Bot) -> None:
    try:
        await bot.send_message(
            chat_id=item.telegram_id,  # type: ignore[attr-defined]
            text=bot_repl.send_messages_end_pay(item.device_name),  # type: ignore[attr-defined]
        )
        log.info(
            "subscription_expiry_notified",
            device_name=item.device_name,  # type: ignore[attr-defined]
            end_date=str(item.end_date),  # type: ignore[attr-defined]
        )
    except Exception:
        log.exception(
            "subscription_expiry_notification_failed",
            telegram_id=item.telegram_id,  # type: ignore[attr-defined]
        )
