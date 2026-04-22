from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.common.bot.cbdata import (
    AdminConfirmCallback,
    DeviceConfCallback,
    DeviceDeleteCallback,
    DeviceErrorCallback,
    SettingsCallback,
    VpnCallback,
)
from src.common.bot.keyboards.user_actions import (
    ActualTariff,
    CallbackAction,
    ChoiceType,
    DeviceType,
    PaymentStatus,
    TARIFF_MATRIX,
    VpnAction,
)
from src.common.bot.lexicon.lexicon import LEXICON_INLINE_DEVICE_RU, LEXICON_INLINE_RU


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
                    text=(LEXICON_INLINE_RU[button] if button in LEXICON_INLINE_RU else button),
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


def get_keyboard_payment_link() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 В меню", callback_data="start")]]
    )


def get_keyboard_type_device(action: str, referral_id: int | None = None) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for dev in DeviceType:
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=LEXICON_INLINE_DEVICE_RU[dev],
                    callback_data=VpnCallback(
                        action=action,
                        device=dev,
                        device_limit=1 if action == VpnAction.REFERRAL else None,
                        duration=1 if action == VpnAction.REFERRAL else 0,
                        referral_id=referral_id,
                        payment=0 if action == VpnAction.REFERRAL else None,
                        balance=0 if action == VpnAction.REFERRAL else None,
                        choice=(ChoiceType.STOP if action == VpnAction.REFERRAL else None),
                        payment_status=(
                            PaymentStatus.SUCCESS if action == VpnAction.REFERRAL else None
                        ),
                    ).pack(),
                )
            ]
        )
    return keyboard


def get_keyboard_device_count(
    action: str, device: str, referral_id: int | None = None
) -> InlineKeyboardMarkup:
    """Шаг 1.5: выбор количества устройств."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for count, label in [(1, "1 устройство"), (2, "2 устройства"), (3, "3 устройства")]:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=label,
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    device_limit=count,
                    duration=0,
                    referral_id=referral_id,
                ).pack(),
            )
        ])
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
    action: str,
    device: str,
    device_limit: int = 1,
    referral_id: int | None = None,
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    prices = TARIFF_MATRIX[device_limit]
    for months, label in [(1, "1 мес"), (3, "3 мес"), (6, "6 мес"), (12, "12 мес")]:
        price = prices[months]
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{label} — {price} руб.",
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    device_limit=device_limit,
                    duration=months,
                    referral_id=referral_id,
                    payment=price,
                ).pack(),
            )
        ])
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
    action: str,
    device: str,
    duration: int,
    balance: int,
    payment: int,
    referral_id: int | None,
    device_limit: int = 1,
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.YES],
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    device_limit=device_limit,
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
                    device_limit=device_limit,
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


def get_keyboard_devices(devices: list, conf=None) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for device in devices:
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=device.device_name,
                    callback_data=DeviceConfCallback(device_id=device.id).pack(),
                )
            ]
        )
    menu = get_basic_menu()
    for i in menu:
        keyboard.inline_keyboard.append(i)
    return keyboard


def get_keyboard_devices_for_error(devices: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for device in devices:
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=device.device_name,
                    callback_data=DeviceErrorCallback(device_id=device.id).pack(),
                )
            ]
        )
    return keyboard


def get_keyboard_devices_for_del(devices: list[str]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for device in devices:
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{device.device_name}",
                    callback_data=DeviceDeleteCallback(device_id=device.id).pack(),
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
                callback_data=VpnCallback(action=CallbackAction.NEW_SUB, device=None).pack(),
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
    device_limit: int = 1,
):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.PAYMENT_SUCCESS],
                callback_data=VpnCallback(
                    action=action,
                    device=device,
                    device_limit=device_limit,
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
                    device_limit=device_limit,
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


def get_keyboard_skip_email() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text="Пропустить ⏩",
                callback_data="skip_email",
            )
        ]
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
                callback_data=SettingsCallback(platform="android_phone").pack(),
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.SETTINGS_IOS],
                callback_data=SettingsCallback(platform="ios").pack(),
            )
        ]
    )
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.SETTINGS_DESKTOP],
                callback_data=SettingsCallback(platform="desktop").pack(),
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


def get_keyboard_admin_confirm(pending_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=AdminConfirmCallback(
                    pending_id=pending_id, action="confirm"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=AdminConfirmCallback(
                    pending_id=pending_id, action="reject"
                ).pack(),
            ),
        ]
    ])
    return keyboard


def get_keyboard_vpn_received() -> InlineKeyboardMarkup:
    """Клавиатура после получения VPN-ключа: инструкция + главное меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📋 Инструкция по подключению",
                callback_data=CallbackAction.SUPPORT_HELP,
            )
        ],
        [
            InlineKeyboardButton(
                text=LEXICON_INLINE_RU[CallbackAction.START],
                callback_data=CallbackAction.START,
            )
        ],
    ])
    return keyboard
