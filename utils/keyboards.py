from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db import ActualTariff


def get_keyboard_type_device(types: str = "set_device"):
    device = ["📱 iOS (iPhone, iPad)", "📱 Android", "💻 Компьютер (Windows, MacOS)"]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    but_lst = []
    for dev in device:
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=dev, callback_data=f"{types}:{dev.split()[1]}")]
        )
    return keyboard


def get_keyboard_type_comp(types: str = "device"):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="💻 Windows", callback_data=f"{types}:Windows")]
    )
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="💻 MacOS", callback_data=f"{types}:MacOS")]
    )
    return keyboard


def get_keyboard_tariff():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=f"1 мес {ActualTariff.month_1} руб.",
                callback_data=f"tariff:{ActualTariff.month_1}:1",
            ),
            InlineKeyboardButton(
                text=f"3 мес {ActualTariff.month_3} руб.",
                callback_data=f"tariff:{ActualTariff.month_3}:3",
            ),
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=f"6 мес {ActualTariff.month_6} руб.",
                callback_data=f"tariff:{ActualTariff.month_6}:6",
            ),
            InlineKeyboardButton(
                text=f"12 мес {ActualTariff.month_12} руб.",
                callback_data=f"tariff:{ActualTariff.month_12}:12",
            ),
        ]
    )
    return keyboard


def get_keyboard_tariff_for_update():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=f"1 мес {ActualTariff.month_1} руб.",
                callback_data=f"uptar:{ActualTariff.month_1}:1",
            ),
            InlineKeyboardButton(
                text=f"3 мес {ActualTariff.month_3} руб.",
                callback_data=f"uptar:{ActualTariff.month_3}:3",
            ),
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=f"6 мес {ActualTariff.month_6} руб.",
                callback_data=f"uptar:{ActualTariff.month_6}:6",
            ),
            InlineKeyboardButton(
                text=f"12 мес {ActualTariff.month_12} руб.",
                callback_data=f"uptar:{ActualTariff.month_12}:12",
            ),
        ]
    )
    return keyboard

def get_keyboard_yes_or_no():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=f"✅ Да, подтверждаю", callback_data=f"finally:Да"
            ),
            InlineKeyboardButton(
                text=f"❌ Нет, передумал", callback_data=f"finally:Нет"
            ),
        ]
    )
    return keyboard

def get_keyboard_yes_or_no_for_update():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=f"✅ Да, подтверждаю", callback_data=f"reup_finally:Да"
            ),
            InlineKeyboardButton(
                text=f"❌ Нет, передумал", callback_data=f"reup_finally:Нет"
            ),
        ]
    )
    return keyboard


def get_keyboard_devices(devices: list[str], conf):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for device in devices:
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{device.device_name}", callback_data=f"{conf}:{device.id}"
                )
            ]
        )
    menu = get_basic_menu()
    for i in menu:
        keyboard.inline_keyboard.append(i)
    return keyboard


def get_keyboard_devices_for_del(devices: list[str]):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for device in devices:
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{device.device_name}",
                    callback_data=f"appr_del_device:{device.id}",
                )
            ]
        )
    return keyboard


def get_basic_menu():
    keyboard = []
    keyboard.append(
        [
            InlineKeyboardButton(text=f"➕ Добавить устр.", callback_data=f"added"),
            InlineKeyboardButton(text=f"➖ Удалить устр.", callback_data=f"del"),
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(text=f"🏠 Главное меню", callback_data=f"start"),
            InlineKeyboardButton(text=f"🆘 Помощь", callback_data=f"help"),
        ]
    )
    return keyboard


def get_keyboard_start():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="☠️ Не работает VPN", callback_data=f"error")]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text="Мои устройства 📱 💻", callback_data="mydevices"
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="Помощь 🆘 ", callback_data=f"help")]
    )
    return keyboard


def get_keyboard_for_details_device(device_name: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="Продлить подписку 💳", callback_data=f"up_tar:{device_name}")]
        )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text="Мои устройства 📱 💻", callback_data="mydevices")]


            )
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="Помощь 🆘 ", callback_data="help")]
    )

    return keyboard


def get_keyboard_approve_payment_or_cancel():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="Я оплатил ✅", callback_data="success")]
    )
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="Отмена ❌", callback_data="mydevices")]
    )
    return keyboard
def get_keyboard_approve_payment_or_cancel_for_update():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="Я оплатил ✅", callback_data="fup_success")]
    )
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="Отмена ❌", callback_data="mydevices")]
    )
    return keyboard


def return_start():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="start")]
    )
    return keyboard


def get_keyboard_help():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="☠️ Не работает VPN", callback_data=f"error")]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text="📱 Настройка на Android", callback_data=f"settings:android"
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text="📱 Настройка на iPhone(iPad)", callback_data=f"settings:iphone"
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=" 💻 Настройка на Компьютер (Windows, MacOS)",
                callback_data=f"settings:computer",
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=f"start")]
    )
    return keyboard
