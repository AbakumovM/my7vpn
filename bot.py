import asyncio
import logging
import os

from aiogram import BaseMiddleware, Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from commands import set_commands
from handlers import router
from utils.scheduler import setup_scheduler

load_dotenv(".env")
logger = logging.getLogger(__name__)


class ResetStateMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data: dict):
        # Проверяем, является ли событие командой (начинается с "/")
        if event.text and event.text.startswith("/"):
            # Получаем FSMContext из текущих данных (data["state"])
            state: FSMContext = data.get("state")
            if state is not None:
                current_state = await state.get_state()  # Текущее состояние FSM
                if current_state is not None:  # Если есть активное состояние
                    await state.clear()  # Сбрасываем состояние

        # Продолжаем выполнение следующего middleware или handler
        return await handler(event, data)


async def main():
    bot = Bot(
        token=os.getenv("BOT_TOKEN"),
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )
    dp = Dispatcher(
        storage=MemoryStorage()
    )  # говорит о том, что все данные бота, которые мы не сохраняем в БД (к примеру состояния), будут стёрты при перезапуске
    dp.message.middleware(ResetStateMiddleware())
    dp.include_routers(router)
    await bot.delete_webhook(
        drop_pending_updates=True
    )  # удаляет все обновления, которые произошли после последнего завершения работы бота.
    await set_commands(bot)
    scheduler = setup_scheduler(bot)
    scheduler.start()
    job = scheduler.get_job("check_subscriptions")
    if job and job.next_run_time:
        next_run = job.next_run_time
        logger.info("🚀 Планировщик запущен")
        logger.info(
            f"📌 Следующее уведомление: {next_run.strftime('%d.%m.%Y %H:%M:%S %Z')}"
        )
    else:
        print("⚠️ Задача не будет выполнена (время уже прошло?)")
    await dp.start_polling(
        bot, allowed_updates=dp.resolve_used_update_types()
    )  # запускает бота, который будет получать обновления через Long Polling
    logger.info("Bot успешно запущен")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] - %(levelname)s - %(name)s - %(message)s",
    )

    asyncio.run(main())
