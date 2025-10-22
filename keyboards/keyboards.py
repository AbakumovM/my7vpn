from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from lexicon.lexicon import LEXICON_INLINE_DEVICE_RU, LEXICON_INLINE_RU
from keyboards.user_actions import (
    ActualTariff,
    CallbackAction,
    ChoiceType,
    DeviceType,
    PaymentStatus,
    VpnAction,
)
from utils.cbdata import VpnCallback


# Функция для формирования инлайн-клавиатуры на лету
def create_inline_kb(width: int, *args: str, **kwargs: str) -> InlineKeyboardMarkup:

    # Инициализируем билдер
    kb_builder = InlineKeyboardBuilder()
    # Инициализируем список для кнопок
    buttons: list[InlineKeyboardButton] = []

    # Заполняем список кнопками из аргументов args и kwargs
    if args:
        for button in args:
            buttons.append(
                InlineKeyboardButton(
                    text=(
                        LEXICON_INLINE_RU[button]
                        if button in LEXICON_INLINE_RU
                        else button
                    ),
                    callback_data=button,
                )
            )
    if kwargs:
        for button, text in kwargs.items():
            buttons.append(InlineKeyboardButton(text=text, callback_data=button))

    # Распаковываем список с кнопками в билдер методом `row` c параметром `width`
    kb_builder.row(*buttons, width=width)

    # Возвращаем объект инлайн-клавиатуры
    return kb_builder.as_markup()


def get_keyboard_type_device(
    action: str, referral_id: int | None = None
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for dev in DeviceType:
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=LEXICON_INLINE_DEVICE_RU[dev],
                    callback_data=VpnCallback(
                        action=action,
                        device=dev,
                        duration=1 if action == VpnAction.REFERRAL else 0,
                        referral_id=referral_id,
                        payment=0 if action == VpnAction.REFERRAL else None,
                        balance=0 if action == VpnAction.REFERRAL else None,
                        choice=(
                            ChoiceType.STOP if action == VpnAction.REFERRAL else None
                        ),
                        payment_status=(
                            PaymentStatus.SUCCESS
                            if action == VpnAction.REFERRAL
                            else None
                        ),
                    ).pack(),
                )
            ]
        )
    return keyboard


def get_keyboard_type_comp(types: str = "device") -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_DEVICE_RU[DeviceType.COMPUTER_WINDOWS],
                callback_data=f"{types}:{DeviceType.COMPUTER_WINDOWS}",
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_DEVICE_RU[DeviceType.COMPUTER_MACOS],
                callback_data=f"{types}:{DeviceType.COMPUTER_MACOS}",
            )
        ]
    )
    return keyboard


def get_keyboard_tariff(
    action: str, device: str, referral_id: int | None = None
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=f"1 мес {ActualTariff.MONTH_1} руб.",
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    duration=1,
                    referral_id=referral_id,
                    payment=ActualTariff.MONTH_1,
                ).pack(),
            ),
            InlineKeyboardButton(
                text=f"3 мес {ActualTariff.MONTH_3} руб.",
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    duration=3,
                    referral_id=referral_id,
                    payment=ActualTariff.MONTH_3,
                ).pack(),
            ),
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=f"6 мес {ActualTariff.MONTH_6} руб.",
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    duration=6,
                    referral_id=referral_id,
                    payment=ActualTariff.MONTH_6,
                ).pack(),
            ),
            InlineKeyboardButton(
                text=f"12 мес {ActualTariff.MONTH_12} руб.",
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    duration=12,
                    referral_id=referral_id,
                    payment=ActualTariff.MONTH_12,
                ).pack(),
            ),
        ]
    )
    return keyboard


def get_keyboard_tariff_for_update() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=f"1 мес {ActualTariff.MONTH_12} руб.",
                callback_data=f"uptar:{ActualTariff.MONTH_1}:1",
            ),
            InlineKeyboardButton(
                text=f"3 мес {ActualTariff.MONTH_3} руб.",
                callback_data=f"uptar:{ActualTariff.MONTH_3}:3",
            ),
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=f"6 мес {ActualTariff.MONTH_6} руб.",
                callback_data=f"uptar:{ActualTariff.MONTH_6}:6",
            ),
            InlineKeyboardButton(
                text=f"12 мес {ActualTariff.MONTH_12} руб.",
                callback_data=f"uptar:{ActualTariff.MONTH_12}:12",
            ),
        ]
    )
    return keyboard


def get_keyboard_yes_or_no() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.YES],
                callback_data=f"finally:{CallbackAction.YES}",
            ),
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.NO],
                callback_data=f"finally:{CallbackAction.NO}",
            ),
        ]
    )
    return keyboard


def get_keyboard_yes_or_no_for_update(
    action, device, duration, balance, payment, referral_id
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.YES],
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    duration=duration,
                    referral_id=referral_id,
                    payment=payment,
                    balance=balance,
                    choice="yes",
                ).pack(),
            ),
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.NO],
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    duration=duration,
                    referral_id=referral_id,
                    payment=payment,
                    balance=balance,
                    choice="no",
                ).pack(),
            ),
        ]
    )
    return keyboard


def get_keyboard_device_test():
    pass


def get_keyboard_devices(devices: list[str], conf) -> InlineKeyboardMarkup:
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


def get_keyboard_devices_for_del(devices: list[str]) -> InlineKeyboardMarkup:
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


def get_basic_menu() -> list[list[InlineKeyboardButton]]:
    keyboard = []
    keyboard.append(
        [
            InlineKeyboardButton(
                text="➕ Добавить устр.",
                callback_data=VpnCallback(
                    action=CallbackAction.NEW_SUB, device=None
                ).pack(),
            ),
            InlineKeyboardButton(text="➖ Удалить устр.", callback_data="del"),
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.START],
                callback_data=CallbackAction.START,
            ),
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.SUPPORT_HELP],
                callback_data=CallbackAction.SUPPORT_HELP,
            ),
        ]
    )
    return keyboard


def get_keyboard_start() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.VPN_ERROR],
                callback_data=CallbackAction.VPN_ERROR,
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.LIST_DEVICES],
                callback_data=CallbackAction.LIST_DEVICES,
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.SUPPORT_HELP],
                callback_data=CallbackAction.SUPPORT_HELP,
            )
        ]
    )
    return keyboard


def get_keyboard_for_details_device(device_name: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.RENEW_SUB],
                callback_data=VpnCallback(
                    action=CallbackAction.RENEW_SUB, device=device_name
                ).pack(),
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.LIST_DEVICES],
                callback_data=CallbackAction.LIST_DEVICES,
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.SUPPORT_HELP],
                callback_data=CallbackAction.SUPPORT_HELP,
            )
        ]
    )

    return keyboard


def get_keyboard_approve_payment_or_cancel(
    action: str,
    device: str,
    duration: int,
    referral_id: int,
    payment: int,
    balance: int,
    choice: str,
):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.PAYMENT_SUCCESS],
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    duration=duration,
                    referral_id=referral_id,
                    payment=payment,
                    balance=balance,
                    choice=choice,
                    payment_status=PaymentStatus.SUCCESS,
                ).pack(),
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.CANCEL],
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    duration=duration,
                    referral_id=referral_id,
                    payment=payment,
                    balance=balance,
                    choice=choice,
                    payment_status=PaymentStatus.FAILED,
                ).pack(),
            )
        ]
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
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.START],
                callback_data=CallbackAction.START,
            )
        ]
    )
    return keyboard


def get_keyboard_help():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.VPN_ERROR],
                callback_data=CallbackAction.VPN_ERROR,
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.SETTINGS_ANDROID_PHONE],
                callback_data=CallbackAction.SETTINGS_ANDROID_PHONE,
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.SETTINGS_IOS],
                callback_data=CallbackAction.SETTINGS_IOS,
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.SETTINGS_DESKTOP],
                callback_data=CallbackAction.SETTINGS_DESKTOP,
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.SETTINGS_TV],
                url="https://telegra.ph/Instrukciya-po-nastrojke-VPN-Key-na-Android-TV-08-27",
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.START],
                callback_data=CallbackAction.START,
            )
        ]
    )

    return keyboard
