from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat

from src.common.bot.lexicon.lexicon import LEXICON_COMMANDS_RU
from src.infrastructure.config import app_config

_ADMIN_COMMANDS: dict[str, str] = {
    **LEXICON_COMMANDS_RU,
    "migrate_all": "🔄 Миграция пользователей на Remnawave",
    "admin_stats": "📊 Статистика подписчиков",
    "admin_expiring": "⏳ Истекающие подписки",
    "admin_churn": "📉 Отток подписчиков",
    "admin_user": "👤 Инфо по пользователю",
}


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command=command, description=description)
        for command, description in LEXICON_COMMANDS_RU.items()
    ]
    await bot.set_my_commands(commands)

    admin_commands = [
        BotCommand(command=command, description=description)
        for command, description in _ADMIN_COMMANDS.items()
    ]
    await bot.set_my_commands(
        admin_commands,
        scope=BotCommandScopeChat(chat_id=app_config.bot.admin_id),
    )
