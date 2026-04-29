import structlog
from aiogram import Router, types
from aiogram.filters import Command

from src.common.bot.cbdata import SettingsCallback
from src.common.bot.keyboards.keyboards import (
    get_keyboard_instruction_detail,
    get_keyboard_instruction_platforms,
)
from src.common.bot.lexicon.text_manager import bot_repl

log = structlog.get_logger(__name__)
router = Router()


@router.message(Command("help"))
async def handle_help_command(msg: types.Message) -> None:
    await msg.answer(
        "📖 <b>Инструкция по подключению</b>\n\nВыберите вашу платформу:",
        reply_markup=get_keyboard_instruction_platforms(),
    )


@router.callback_query(SettingsCallback.filter())
async def handle_settings(call: types.CallbackQuery, callback_data: SettingsCallback) -> None:
    text = bot_repl.get_instruction(callback_data.platform)
    await call.message.answer(
        text,
        reply_markup=get_keyboard_instruction_detail(),
        disable_web_page_preview=True,
    )
    await call.answer()
