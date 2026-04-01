import asyncio
import logging
import os

from typing import Any, Awaitable, Callable, Union

from aiogram import BaseMiddleware, Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from database.device_service import get_count_device_for_user
from database.user_service import get_user
from keyboards.commands import set_commands
from handlers import router
from utils.scheduler import setup_scheduler
from config.config_app import app_config

logger = logging.getLogger(__name__)


SERVICE_CLOSED_MESSAGE = (
    "🚫 К сожалению, сервис временно не принимает новых пользователей.\n\n"
    "Если у вас есть вопросы — напишите @my7vpnadmin."
)


class RegistrationClosedMiddleware(BaseMiddleware):
    """Блокирует весь доступ к боту для пользователей без устройств, если регистрация закрыта."""

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Union[types.Message, types.CallbackQuery],
        data: dict[str, Any],
    ) -> Any:
        if app_config.service.registration_open:
            return await handler(event, data)

        telegram_id = event.from_user.id

        # Админу доступ не блокируем
        if telegram_id == app_config.bot.admin_id:
            return await handler(event, data)

        user = await get_user(telegram_id)
        if user is None:
            # Пользователь даже не зарегистрирован
            if isinstance(event, types.Message):
                await event.answer(SERVICE_CLOSED_MESSAGE)
            else:
                await event.message.answer(SERVICE_CLOSED_MESSAGE)
                await event.answer()
            return

        device_count = await get_count_device_for_user(telegram_id)
        if device_count == 0:
            if isinstance(event, types.Message):
                await event.answer(SERVICE_CLOSED_MESSAGE)
            else:
                await event.message.answer(SERVICE_CLOSED_MESSAGE)
                await event.answer()
            return

        return await handler(event, data)


class NewDeviceBlockMiddleware(BaseMiddleware):
    """Блокирует добавление новых устройств для существующих пользователей."""

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: types.CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        if app_config.service.new_devices_allowed:
            return await handler(event, data)

        # Админу доступ не блокируем
        if event.from_user.id == app_config.bot.admin_id:
            return await handler(event, data)

        # Проверяем callback_data на действия добавления нового устройства
        if event.data and event.data.startswith("vpn:"):
            # VpnCallback формат — проверяем action
            parts = event.data.split(":")
            # action — второй элемент после "vpn:"
            if len(parts) > 1 and parts[1] in ("new", "referral"):
                await event.message.edit_text(
                    "🚫 К сожалению, добавление новых устройств временно приостановлено.\n\n"
                    "Вы можете продлить подписку на существующие устройства."
                )
                await event.answer()
                return

        return await handler(event, data)


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
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] - %(levelname)s - %(name)s - %(message)s",
    )
    logger.info("Starting bot")
    bot = Bot(
        token=app_config.bot.token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )
    dp = Dispatcher(
        storage=MemoryStorage()
    )  # говорит о том, что все данные бота, которые мы не сохраняем в БД (к примеру состояния), будут стёрты при перезапуске

    dp.include_routers(router)

    dp.message.middleware(RegistrationClosedMiddleware())
    dp.callback_query.middleware(RegistrationClosedMiddleware())
    dp.callback_query.middleware(NewDeviceBlockMiddleware())
    dp.message.middleware(ResetStateMiddleware())

    await bot.delete_webhook(
        drop_pending_updates=True
    )  # удаляет все обновления, которые произошли после последнего завершения работы бота.
    dp.startup.register(set_commands)
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


if __name__ == "__main__":
    asyncio.run(main())
