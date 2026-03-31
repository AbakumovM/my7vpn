import structlog
from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from dishka.integrations.aiogram import FromDishka

from src.apps.device.application.interfaces.view import DeviceView
from src.common.bot.keyboards.keyboards import (
    create_inline_kb,
    get_keyboard_devices,
    get_keyboard_help,
)
from src.common.bot.keyboards.user_actions import CallbackAction
from src.common.bot.lexicon.text_manager import bot_repl
from src.infrastructure.config import app_config

log = structlog.get_logger(__name__)
router = Router()

ADMIN_ID = app_config.bot.admin_id


@router.callback_query(F.data == CallbackAction.VPN_ERROR)
async def handle_vpn_error(
    call: types.CallbackQuery,
    device_view: FromDishka[DeviceView],
) -> None:
    try:
        devices = await device_view.list_for_user(call.from_user.id)
        if devices:
            await call.message.answer(
                "С каким устройством у вас возникли проблемы? Пожалуйста, выберите из списка ниже:",
                reply_markup=get_keyboard_devices(devices, CallbackAction.DEVICE_ERROR),
            )
        else:
            await call.message.answer("У вас нет активных устройств")
    except Exception:
        log.exception("handle_vpn_error_error")
        await call.message.answer(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data.startswith(CallbackAction.DEVICE_ERROR))
async def handle_device_error_report(
    call: types.CallbackQuery,
    bot: Bot,
) -> None:
    device_id = call.data.split(":")[2]
    log.info("vpn_error_reported", device_id=device_id)
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"Пользователь сообщил о проблеме с подключением!\n"
            f"👤 Имя: {call.from_user.username}\n"
            f"🆔 ID: {call.from_user.id}|{device_id}"
        ),
    )
    keyboard = create_inline_kb(
        1,
        CallbackAction.VPN_ERROR,
        CallbackAction.LIST_DEVICES,
        CallbackAction.SUPPORT_HELP,
    )
    await call.message.answer(bot_repl.get_message_admin_error(), reply_markup=keyboard)


@router.callback_query(F.data == CallbackAction.SUPPORT_HELP)
async def handle_help_callback(call: types.CallbackQuery) -> None:
    await call.message.answer(bot_repl.get_help_text(), reply_markup=get_keyboard_help())


@router.message(Command("help"))
async def handle_help_command(msg: types.Message) -> None:
    await msg.answer(bot_repl.get_help_text(), reply_markup=get_keyboard_help())


@router.callback_query(F.data.startswith("settings:"))
async def handle_settings(call: types.CallbackQuery) -> None:
    settings_map = {
        "android_phone": bot_repl.get_android_settings(),
        "desktop": bot_repl.get_computer_settings(),
        "ios": bot_repl.get_settings_iphone(),
    }
    settings_type = call.data.split(":")[1]
    text = settings_map.get(settings_type, "Настройки не найдены")
    await call.message.answer(
        text,
        reply_markup=get_keyboard_help(),
        disable_web_page_preview=True,
    )
