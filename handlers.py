# -*- coding: utf-8 -*-
import logging

from aiogram import Bot, F, Router, types
from aiogram.filters import Command

from database.db_service import create_vpn, get_referral_by_id, get_referral_code
from database.device_service import (
    del_device,
    get_count_device_for_user,
    get_devices_users,
    get_full_info_device,
    update_tariff_from_device,
)
from database.user_service import (
    get_balance_user,
    get_or_create_user,
    update_balance_user,
)
from keyboards.user_actions import CallbackAction, ChoiceType, PaymentStatus, VpnAction
from utils.cbdata import VpnCallback
from utils.files import get_photo_for_pay
from keyboards.keyboards import (
    create_inline_kb,
    get_keyboard_approve_payment_or_cancel,
    get_keyboard_devices,
    get_keyboard_devices_for_del,
    get_keyboard_for_details_device,
    get_keyboard_help,
    get_keyboard_start,
    get_keyboard_tariff,
    get_keyboard_type_device,
    get_keyboard_yes_or_no_for_update,
    return_start,
)

from lexicon.text_manager import bot_repl
from config.config_app import app_config

logger = logging.getLogger(__name__)

ADMIN_ID = app_config.bot.admin_id
LINK = app_config.payment.payment_url
router = Router()


@router.message(Command(CallbackAction.START))
async def get_start(msg: types.Message):
    referral = msg.text.split(" ")[1] if len(msg.text.split(" ")) > 1 else None
    if referral:
        referral_by = await get_referral_by_id(referral)
        if not referral_by:
            await msg.answer(
                bot_repl.get_message_error_referral(), reply_markup=return_start()
            )
            return

        user = await get_or_create_user(msg.from_user.id, referral_by)
        if user.free_months:
            await msg.answer(
                text="❌ Вы уже использовали бесплатный месяц ранее",
                reply_markup=return_start(),
            )
            return

        await msg.answer(
            bot_repl.get_start_message_free_month(msg.from_user.full_name),
            reply_markup=get_keyboard_type_device(VpnAction.REFERRAL, referral_by),
        )
        return
    else:
        user = await get_or_create_user(msg.from_user.id)
        device = await get_count_device_for_user(msg.from_user.id)
        if device > 0:
            keyboard = create_inline_kb(
                1,
                CallbackAction.VPN_ERROR,
                CallbackAction.LIST_DEVICES,
                CallbackAction.SUPPORT_HELP,
            )
            await msg.answer(
                bot_repl.get_start(msg.from_user.full_name, device, user.balance),
                reply_markup=keyboard,
            )
        else:
            await msg.answer(
                bot_repl.get_start_message(msg.from_user.full_name),
                reply_markup=get_keyboard_type_device(VpnAction.NEW),
            )
        return


@router.callback_query(F.data.in_([CallbackAction.CANCEL, CallbackAction.START]))
async def get_start_callback(call: types.CallbackQuery):
    try:
        user = await get_or_create_user(call.from_user.id)
        device = await get_count_device_for_user(call.from_user.id)
        keyboard = create_inline_kb(
            1,
            CallbackAction.VPN_ERROR,
            CallbackAction.LIST_DEVICES,
            CallbackAction.SUPPORT_HELP,
        )
        await call.message.answer(
            bot_repl.get_start(call.from_user.full_name, device, user.balance),
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"Произошла ошибка в функции get_start_callback: {e}")
        await call.message.edit_text(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.message(Command("devices"))
async def get_devices(msg: types.Message):
    try:
        devices = await get_devices_users(msg.from_user.id)
        if devices is not None:
            keyboard = get_keyboard_devices(devices, "conf")
            await msg.answer(
                text=bot_repl.get_message_devices(len(devices)), reply_markup=keyboard
            )
        else:
            await msg.answer(
                "У вас нет активных устройств", reply_markup=get_keyboard_start()
            )
    except Exception as e:
        logger.error(
            f"Произошла ошибка в функции get_devices, id {msg.from_user.id}: {e}"
        )
        await msg.message.answer(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data == CallbackAction.LIST_DEVICES)
async def handle_my_devices_callback(call: types.CallbackQuery):
    try:
        devices = await get_devices_users(call.from_user.id)
        if devices is not None:
            keyboard = get_keyboard_devices(devices, "conf")
            await call.message.answer(
                text=bot_repl.get_message_devices(len(devices)), reply_markup=keyboard
            )
        else:
            await call.message.answer("У вас нет активных устройств")
    except Exception as e:
        logger.error(
            f"Произошла ошибка в функции handle_my_devices_callback, id {call.from_user.id}: {e}"
        )
        await call.message.answer(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data.startswith("del"))
async def delete_device(call: types.CallbackQuery):
    try:
        device = await get_devices_users(call.from_user.id)
        if device is None:
            await call.message.answer("У вас нет активных устройств")
            return
        keyboard = get_keyboard_devices_for_del(device)
        await call.message.answer(
            "Какое устройство вы хотите отключить?", reply_markup=keyboard
        )
    except Exception as e:
        logger.error(
            f"Произошла ошибка в функции delete_device, id {call.from_user.id}: {e}"
        )
        await call.message.answer(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data.startswith("appr_del_device"))
async def del_device_approve(call: types.CallbackQuery, bot: Bot):
    device_id = call.data.split(":")[1]
    try:
        result = await del_device(int(device_id))
        await call.message.edit_text("Устройство удалено")
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ Пользователь удалил у себя VPN!\n"
            f"👤 Имя: {call.from_user.username}\n"
            f"🆔 ID: {call.from_user.id}\n"
            f"📋 Девайс: {result}",
        )
        logger.info(
            f"Пользователь {call.from_user.id} удалил у себя устройство {result}."
        )
    except Exception as e:
        logger.error(
            f"Произошла ошибка в функции del_device_approve, id {call.from_user.id}: {e}"
        )
        await call.message.edit_text(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data.startswith("conf"))
async def conf_device_for_user(call: types.CallbackQuery):
    device_id = int(call.data.split(":")[1])
    result = await get_full_info_device(device_id)
    text, device_name = bot_repl.generate_device_info_message(result)
    await call.message.answer(
        text=text,
        reply_markup=get_keyboard_for_details_device(device_name=result["device_name"]),
    )


@router.callback_query(F.data == CallbackAction.VPN_ERROR)
async def error_help_user(call: types.CallbackQuery):
    try:
        devices = await get_devices_users(call.from_user.id)
        if devices is not None:
            await call.message.answer(
                "С каким устройством у вас возникли проблемы? Пожалуйста, выберите из списка ниже:",
                reply_markup=get_keyboard_devices(devices, CallbackAction.DEVICE_ERROR),
            )
        else:
            await call.message.answer("У вас нет активных устройств")
    except Exception as e:
        logger.error(
            f"Произошла ошибка в функции error_help_user, id {call.from_user.id}: {e}"
        )
        await call.message.answer(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data.startswith(CallbackAction.DEVICE_ERROR))
async def send_message_error_for_admin(call: types.CallbackQuery, bot: Bot):
    device_id = call.data.split(":")[2]
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Пользователь сообщил о проблеме с подключением!\n"
        f"👤 Имя: {call.from_user.username}\n"
        f"🆔 ID: {call.from_user.id}|{device_id}",
    )
    keyboard = create_inline_kb(
        1,
        CallbackAction.VPN_ERROR,
        CallbackAction.LIST_DEVICES,
        CallbackAction.SUPPORT_HELP,
    )
    await call.message.answer(bot_repl.get_message_admin_error(), reply_markup=keyboard)


@router.callback_query(F.data == CallbackAction.SUPPORT_HELP)
async def get_help_all(call: types.CallbackQuery):
    await call.message.answer(
        bot_repl.get_help_text(), reply_markup=get_keyboard_help()
    )


@router.message(Command(CallbackAction.SUPPORT_HELP))
async def get_help_all_command(msg: types.Message):
    await msg.answer(bot_repl.get_help_text(), reply_markup=get_keyboard_help())


@router.callback_query(F.data.startswith("settings:"))
async def get_settings_android(call: types.CallbackQuery):
    settings = {
        "android_phone": bot_repl.get_android_settings(),
        "desktop": bot_repl.get_computer_settings(),
        "ios": bot_repl.get_settings_iphone(),
    }
    settings_type = call.data.split(":")[1]
    await call.message.answer(
        settings[settings_type],
        reply_markup=get_keyboard_help(),
        disable_web_page_preview=True,
    )


@router.message(Command(CallbackAction.INVITE))
async def invite_user(msg: types.Message):
    referral_code = await get_referral_code(msg.from_user.id)
    keyboard = create_inline_kb(
        1,
        CallbackAction.VPN_ERROR,
        CallbackAction.LIST_DEVICES,
        CallbackAction.SUPPORT_HELP,
    )
    await msg.answer(
        bot_repl.get_message_invite_friend(referral_code),
        reply_markup=keyboard,
    )


@router.callback_query(VpnCallback.filter())
async def test_factory(call: types.CallbackQuery, callback_data: VpnCallback, bot: Bot):
    action = callback_data.action
    device = callback_data.device
    duration = callback_data.duration
    referral_id = callback_data.referral_id
    payment = callback_data.payment
    balance = callback_data.balance
    choice = callback_data.choice
    payment_status = callback_data.payment_status

    if device == None:
        await call.message.edit_text(
            bot_repl.get_message_for_added_device(),
            reply_markup=get_keyboard_type_device(
                action=action, referral_id=referral_id
            ),
        )
        await call.answer()
        return
    if duration == 0:
        await call.message.edit_text(
            "Выберете тариф, который хотите подключить:",
            reply_markup=get_keyboard_tariff(
                action=action, device=device, referral_id=referral_id
            ),
        )
        await call.answer()
        return

    if balance is None:
        user_balance = await get_balance_user(call.from_user.id)
        finally_payment = max(payment - user_balance, 0)
        balance = max(user_balance - payment, 0)
        await call.message.edit_text(
            bot_repl.get_full_info_payment(device, duration, finally_payment, payment),
            reply_markup=get_keyboard_yes_or_no_for_update(
                action=action,
                device=device,
                duration=duration,
                balance=balance,
                payment=finally_payment,
                referral_id=referral_id,
            ),
        )
        await call.answer()
        return
    if choice == ChoiceType.NO or payment_status == PaymentStatus.FAILED:
        keyboard = create_inline_kb(1, CallbackAction.START)
        await call.message.delete()
        await call.message.answer(
            text=bot_repl.send_messages_cancel_choice(), reply_markup=keyboard
        )
        await call.answer()
        return
    if choice == ChoiceType.YES:
        await call.message.delete()
        file_date = await get_photo_for_pay()
        choice = ChoiceType.STOP
        await call.message.answer_photo(
            photo=file_date,
            caption=bot_repl.get_approve_payment(amount=payment, payment_link=LINK),
            reply_markup=get_keyboard_approve_payment_or_cancel(
                action=action,
                device=device,
                duration=duration,
                referral_id=referral_id,
                payment=payment,
                balance=balance,
                choice=choice,
            ),
        )
        await call.answer()
        return
    if action == CallbackAction.NEW_SUB and payment_status == PaymentStatus.SUCCESS:
        result = await create_vpn(
            telegram_id=call.from_user.id,
            device=device,
            period=duration,
            tariff=payment,
        )
        await call.message.delete()
        await call.message.answer(
            text=bot_repl.get_message_success_payment(), reply_markup=return_start()
        )
        await update_balance_user(call.from_user.id, amount=balance)

        await bot.send_message(
            chat_id=ADMIN_ID,
            text=bot_repl.send_message_admin_new_device(
                username=call.from_user.username,
                user_id=call.from_user.id,
                device=result[0],
                duration=duration,
                payment=payment,
            ),
        )

        await call.answer()
        return

    if action == VpnAction.RENEW:
        print(duration, device, payment)
        result = await update_tariff_from_device(device, duration, payment)

        await call.message.delete()
        await call.message.answer(
            text=bot_repl.get_message_success_payment_update(),
            reply_markup=return_start(),
        )

        await update_balance_user(call.from_user.id, amount=balance)

        await bot.send_message(
            chat_id=ADMIN_ID,
            text=bot_repl.send_messages_for_admin_update(
                username=call.from_user.username,
                user_id=call.from_user.id,
                device=device,
                duration=duration,
                payment=payment,
            ),
        )
        await call.answer()
        return
    if action == VpnAction.REFERRAL:
        result = await create_vpn(
            telegram_id=call.from_user.id, device=device, free_month=True
        )
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=bot_repl.send_message_admin_new_user_referral(
                username=call.from_user.username,
                user_id=call.from_user.id,
                device=result[0],
                referral_id=referral_id,
            ),
        )
        await update_balance_user(referral_id, amount=50, referral=True)
        await call.message.edit_text(
            bot_repl.get_message_success_free_month(device), reply_markup=return_start()
        )
        await bot.send_message(
            chat_id=referral_id, text=bot_repl.get_message_new_user_referral()
        )
        await call.answer()
        return
