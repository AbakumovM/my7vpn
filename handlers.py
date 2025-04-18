# -*- coding: utf-8 -*-
import os
from aiogram import Router
from aiogram import types, F, Router
from aiogram.types import BufferedInputFile
from aiogram.filters import Command
from utils.files import get_photo_for_pay
from utils.states import RegisterVpn
from utils.text_manager import bot_repl
from utils.keyboards import (
    get_keyboard_approve_payment_or_cancel,
    get_keyboard_devices,
    get_keyboard_devices_for_del,
    get_keyboard_for_details_device,
    get_keyboard_help,
    get_keyboard_start,
    get_keyboard_tariff,
    get_keyboard_type_comp,
    get_keyboard_type_device,
    get_keyboard_yes_or_no,
    return_start,
)
from aiogram.fsm.context import FSMContext
from aiogram import Bot
from auth import (
    create_vpn,
    del_device,
    get_balance_user,
    get_count_device_for_user,
    get_devices_users,
    get_full_info_device,
    get_or_create_user,
    get_referral_by_id,
    get_referral_code,
    update_balance_user,
)
from dotenv import load_dotenv


load_dotenv(".env")
ADMIN_ID = os.getenv("ADMIN_ID")
LINK = os.getenv("LINK")
router = Router()


@router.message(Command("start"))
async def get_start(msg: types.Message, state: FSMContext):
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
            reply_markup=get_keyboard_type_device("free_set_device"),
        )
        await state.update_data(referral_by=referral_by)
        return
    else:
        user = await get_or_create_user(msg.from_user.id)
        device = await get_count_device_for_user(msg.from_user.id)
        if device > 0:
            await msg.answer(
                bot_repl.get_start(msg.from_user.full_name, device, user.balance),
                reply_markup=get_keyboard_start(),
            )
        else:
            await msg.answer(
                bot_repl.get_start_message(msg.from_user.full_name),
                reply_markup=get_keyboard_type_device(),
            )
        await state.set_state(RegisterVpn.chooising_devise)


@router.callback_query(F.data.startswith("start"))
async def get_start_callback(call: types.CallbackQuery):
    try:
        user = await get_or_create_user(call.from_user.id)
        device = await get_count_device_for_user(call.from_user.id)
        await call.message.answer(
            bot_repl.get_start(call.from_user.full_name, device, user.balance),
            reply_markup=get_keyboard_start(),
        )
    except Exception as e:
        await call.message.edit_text(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )
        


@router.callback_query(F.data.startswith("free_set_device"))
async def get_start_free_month(call: types.CallbackQuery, bot: Bot, state: FSMContext):
    device = call.data.split(":")[1]
    if device in "Компьютер":
        await call.message.answer(
            "Пожалуйста, выберите тип компьютера, для которого вы хотите использовать эти настройки:",
            reply_markup=get_keyboard_type_comp("free_device"),
        )
    else:
        data = await state.get_data()
        await create_vpn(telegram_id=call.from_user.id, device=device, free_month=True)
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"Пользователь хочет подключить VPN по реферальной ссылке!\n"
            f"👤 Имя: {call.from_user.username}\n"
            f"🆔 ID: {call.from_user.id}\n"
            f"🆔 Кто пригласил: {data['referral_by']}"
            f"📋 Критерии: девайс {device}",
        )
        await update_balance_user(data["referral_by"], amount=50, referral=True)
        await call.message.answer(
            bot_repl.get_message_success_free_month(device), reply_markup=return_start()
        )
        await bot.send_message(
            chat_id=data["referral_by"], text=bot_repl.get_message_new_user_referral()
        )
        await state.clear()


@router.callback_query(F.data.startswith("free_device"))
async def set_free_device_comp(call: types.CallbackQuery, bot: Bot, state: FSMContext):
    type_device = call.data.split(":")[1]
    data = await state.get_data()
    await create_vpn(telegram_id=call.from_user.id, device=type_device, free_month=True)
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Пользователь хочет подключить VPN по реферальной ссылке!\n"
        f"👤 Имя: {call.from_user.username}\n"
        f"🆔 ID: {call.from_user.id}\n"
        f"🆔 Кто пригласил: {data['referral_by']}"
        f"📋 Критерии: девайс {type_device}",
    )
    await call.message.answer(
        bot_repl.get_message_success_free_month(type_device),
        reply_markup=return_start(),
    )
    await bot.send_message(
        chat_id=data['referral_by'], text=bot_repl.get_message_new_user_referral()
    )
    await state.clear()


@router.callback_query(F.data.startswith("set_device"))
async def set_device_callback(call: types.CallbackQuery, state: FSMContext):
    device = call.data.split(":")[1]
    if device in "Компьютер":
        await call.message.answer(
            "Пожалуйста, выберите тип компьютера, для которого вы хотите использовать эти настройки:",
            reply_markup=get_keyboard_type_comp(),
        )
    else:
        await state.update_data(device=device)
        await call.message.answer(
            "Выберете тариф, который хотите подключить:",
            reply_markup=get_keyboard_tariff(),
        )


@router.callback_query(F.data.startswith("device"))
async def set_device_comp(call: types.CallbackQuery, state: FSMContext):
    type_device = call.data.split(":")[1]
    await state.update_data(device=type_device)
    await call.message.answer(
        "Выберете тариф, который хотите подключить:", reply_markup=get_keyboard_tariff()
    )


@router.callback_query(F.data.startswith("tariff"))
async def set_tariff_callback(call: types.CallbackQuery, state: FSMContext):
    balance = await get_balance_user(call.from_user.id)
    await call.message.delete()
    tariff = call.data.split(":")[1]
    period = call.data.split(":")[2]
    payment = max(int(tariff) - balance, 0)
    balance = max(balance - int(tariff), 0)
    await state.update_data(
        tariff=tariff, period=period, payment=payment, balance=balance
    )
    data = await state.get_data()
    await call.message.answer(
        bot_repl.get_full_info_payment(data), reply_markup=get_keyboard_yes_or_no()
    )


@router.callback_query(F.data.startswith("finally"))
async def set_finally_vpn(call: types.CallbackQuery, state: FSMContext, bot: Bot):
    answer = call.data.split(":")[1]
    if answer in "Да":
        try:
            await call.message.delete()
            file_date = await get_photo_for_pay()
            photo = BufferedInputFile(file_date, filename="qr_payment.jpeg")
            data = await state.get_data()
            await call.message.answer_photo(
                photo=photo,
                caption=bot_repl.get_approve_payment(
                    amount=data["payment"], balance=data["balance"], payment_link=LINK
                ),
                reply_markup=get_keyboard_approve_payment_or_cancel(),
            )
        except Exception as e:
            await call.message.answer(f"Произошла ошибка, попробуйте еще раз: {e}")
            await state.clear()
    else:
        await state.clear()
        await call.message.answer(
            "Давай еще раз начнем с начала", reply_markup=get_keyboard_type_device()
        )


@router.callback_query(F.data.startswith("success"))
async def success_payment_answer(
    call: types.CallbackQuery, state: FSMContext, bot: Bot
):
    try:
        data = await state.get_data()
        result = await create_vpn(
            call.from_user.id, data["device"], data["period"], data["tariff"]
        )
        await call.message.delete()
        await call.message.answer(
            text=bot_repl.get_message_success_payment(),
            reply_markup=return_start()
        )
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"Пользователь хочет подключить VPN!\n"
            f"👤 Имя: {call.from_user.username}\n"
            f"🆔 ID: {call.from_user.id}\n"
            f"📋 Критерии: девайс {result[0]}, срок {data["period"]}, тариф {data['tariff']}, сколько оплатил {data['payment']}",
        )
        await update_balance_user(call.from_user.id, amount=data["balance"])
    except Exception as e:
        await call.message.answer(f"Произошла ошибка, попробуйте еще раз ! {e}")
        await state.clear()


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
        await msg.message.answer("Произошла ошибка, попробуйте еще раз")


@router.callback_query(F.data.startswith("mydevices"))
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
    except Exception as e:
        await call.message.edit_text(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data.startswith("added"))
async def add_device_for_user(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer(
        bot_repl.get_message_for_added_device(), reply_markup=get_keyboard_type_device()
    )
    await state.set_state(RegisterVpn.chooising_devise)


@router.callback_query(F.data.startswith("conf"))
async def conf_device_for_user(call: types.CallbackQuery):
    device_id = int(call.data.split(":")[1])
    result = await get_full_info_device(device_id)
    text, flag = bot_repl.generate_device_info_message(result)
    await call.message.answer(
        text=text, reply_markup=get_keyboard_for_details_device(flag)
    )


@router.callback_query(F.data.startswith("error"))
async def error_help_user(call: types.CallbackQuery):
    try:
        devices = await get_devices_users(call.from_user.id)
        if devices is not None:
            await call.message.answer(
                "С каким устройством у вас возникли проблемы? Пожалуйста, выберите из списка ниже:",
                reply_markup=get_keyboard_devices(devices, "errdev"),
            )
        else:
            await call.message.answer("У вас нет активных устройств")
    except Exception as e:
        await call.message.answer(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data.startswith("errdev"))
async def send_message_error_for_admin(call: types.CallbackQuery, bot: Bot):
    device_id = call.data.split(":")[1]
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Пользователь сообщил о проблеме с подключением!\n"
        f"👤 Имя: {call.from_user.username}\n"
        f"🆔 ID: {call.from_user.id}|{device_id}",
    )
    await call.message.answer(
        bot_repl.get_message_admin_error(), reply_markup=get_keyboard_start()
    )


@router.callback_query(F.data.startswith("help"))
async def get_help_all(call: types.CallbackQuery):
    await call.message.answer(
        bot_repl.get_help_text(), reply_markup=get_keyboard_help()
    )


@router.message(Command("help"))
async def get_help_all(msg: types.Message):
    await msg.answer(bot_repl.get_help_text(), reply_markup=get_keyboard_help())


@router.callback_query(F.data.startswith("settings"))
async def get_settings_android(call: types.CallbackQuery):
    settings = {
        "android": bot_repl.get_android_settings(),
        "computer": bot_repl.get_computer_settings(),
        "iphone": bot_repl.get_settings_iphone(),
    }
    settings_type = call.data.split(":")[1]
    await call.message.answer(
        settings[settings_type],
        reply_markup=get_keyboard_help(),
        disable_web_page_preview=True,
    )


@router.message(Command("invite"))
async def invite_user(msg: types.Message):
    referral_code = await get_referral_code(msg.from_user.id)
    await msg.answer(
        bot_repl.get_message_invite_friend(referral_code),
        reply_markup=get_keyboard_start(),
    )
