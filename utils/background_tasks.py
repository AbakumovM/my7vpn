import asyncio
import logging
import os
from datetime import datetime
from io import StringIO

from aiogram import Bot
from aiogram.types import BufferedInputFile

from database.db_service import scheduled_payments
from lexicon.text_manager import bot_repl

ADMIN_ID = os.getenv("ADMIN_ID")
logger = logging.getLogger(__name__)


async def check_pending_subscriptions(bot):
    # Логика проверки подписок
    pending = await scheduled_payments()  # твой запрос к БД

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
        report = f"🔔 Отчёт на {datetime.now().strftime('%d.%m.%Y %H:%M')}\n✅ Нет активных подписок, требующих уведомления."

    try:
        await send_long_message(bot, ADMIN_ID, report)
    except Exception as e:
        logger.error(f"Не удалось отправить админу {ADMIN_ID}: {e}")


async def send_long_message(bot: Bot, chat_id: int, text: str, max_len: int = 4000):
    if len(text) <= max_len:
        await bot.send_message(chat_id=chat_id, text=text)
    else:
        buffer = StringIO()
        buffer.write(text)
        buffer.seek(0)
        input_file = BufferedInputFile(
            buffer.getvalue().encode("utf-8"), filename="report.txt"
        )
        await bot.send_document(chat_id=chat_id, document=input_file)


async def send_message_end_payments(item: list, bot: Bot):
    try:
        await bot.send_message(
            chat_id=item.telegram_id,
            text=bot_repl.send_messages_end_pay(item.device_name),
        )
    except Exception as e:
        logger.error(
            f'f"Ошибка отправки уведомления пользователю {item.telegram_id}: {e}'
        )
