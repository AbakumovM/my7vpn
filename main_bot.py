import asyncio
import zoneinfo

import structlog
from aiogram import BaseMiddleware, Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dishka.integrations.aiogram import setup_dishka

from ioc import create_container
from src.apps.device.controllers.bot.router import router as device_router
from src.apps.device.domain.exceptions import (
    DeviceNotFound,
    SubscriptionNotFound,
    UserDeviceNotFound,
)
from src.apps.user.controllers.bot.admin_router import router as admin_router
from src.apps.user.controllers.bot.router import router as user_router
from src.apps.user.domain.exceptions import InsufficientBalance, ReferralNotFound, UserNotFound
from src.common.bot.keyboards.commands import set_commands
from src.common.bot.router import router as common_router
from src.common.scheduler.tasks import send_expiry_notifications
from src.infrastructure.bot.throttling import ThrottlingMiddleware
from src.infrastructure.config import app_config
from src.infrastructure.logging.setup import configure_logging

log = structlog.get_logger(__name__)

ADMIN_ID = app_config.bot.admin_id

_EXPECTED_EXCEPTIONS = (
    UserNotFound,
    InsufficientBalance,
    ReferralNotFound,
    DeviceNotFound,
    SubscriptionNotFound,
    UserDeviceNotFound,
)


async def handle_error(event: types.ErrorEvent, bot: Bot) -> None:
    log.exception("unhandled_error", exc_info=event.exception)

    update = event.update
    chat_id: int | None = None
    if update.message:
        chat_id = update.message.chat.id
    elif update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat.id

    if chat_id is not None:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="Произошла ошибка. Попробуй ещё раз или напиши @my7vpnadmin",
            )
        except Exception:
            pass

    if not isinstance(event.exception, _EXPECTED_EXCEPTIONS):
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🔴 Необработанная ошибка!\n"
                    f"Тип: {type(event.exception).__name__}\n"
                    f"Сообщение: {event.exception}"
                ),
            )
        except Exception:
            pass


class ResetStateMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data: dict) -> None:
        if event.text and event.text.startswith("/"):
            state: FSMContext = data.get("state")
            if state is not None:
                current_state = await state.get_state()
                if current_state is not None:
                    await state.clear()
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Update, data: dict) -> object:
        structlog.contextvars.clear_contextvars()
        from_user: types.User | None = data.get("event_from_user")
        if from_user is not None:
            structlog.contextvars.bind_contextvars(
                telegram_id=from_user.id,
                update_id=event.update_id,
            )
        return await handler(event, data)


async def main() -> None:
    configure_logging(app_config.logging)
    log.info("bot_starting")

    bot = Bot(
        token=app_config.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.errors.register(handle_error)

    container = create_container(app_config)
    setup_dishka(container, router=dp, auto_inject=True)

    dp.include_routers(admin_router, user_router, device_router, common_router)
    dp.message.middleware(ResetStateMiddleware())
    dp.update.outer_middleware(LoggingMiddleware())
    dp.update.outer_middleware(ThrottlingMiddleware())

    dp.startup.register(set_commands)

    scheduler = AsyncIOScheduler(timezone=zoneinfo.ZoneInfo("Europe/Moscow"))
    scheduler.add_job(
        send_expiry_notifications,
        trigger=CronTrigger(hour=10, minute=0),
        id="send_expiry_notifications",
        kwargs={"bot": bot, "container": container},
    )
    scheduler.start()

    job = scheduler.get_job("send_expiry_notifications")
    if job and job.next_run_time:
        log.info(
            "scheduler_next_run",
            next_run=job.next_run_time.strftime("%d.%m.%Y %H:%M:%S %Z"),
        )

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
