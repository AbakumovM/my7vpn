import asyncio
import logging
from aiogram import BaseMiddleware, Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from handlers import router
from commands import set_commands
import os
from dotenv import load_dotenv

load_dotenv(".env")


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

    await dp.start_polling(
        bot, allowed_updates=dp.resolve_used_update_types()
    )  # запускает бота, который будет получать обновления через Long Polling


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    asyncio.run(main())
