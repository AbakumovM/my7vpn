from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.common.bot.cbdata import (
    AdminConfirmCallback,
    SettingsCallback,
    VpnCallback,
)
from src.common.bot.keyboards.user_actions import (
    TARIFF_MATRIX,
    CallbackAction,
    ChoiceType,
    PaymentStatus,
    VpnAction,
)
from src.common.bot.lexicon.lexicon import LEXICON_INLINE_RU
from src.infrastructure.config import app_config


def get_keyboard_payment_link() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 В меню", callback_data="start")]]
    )


def get_keyboard_main_menu(has_subscription: bool) -> InlineKeyboardMarkup:
    """Главное меню — сетка 2×2 + 2×1. URL-кнопки для кабинета и поддержки."""
    if has_subscription:
        rows = [
            [
                InlineKeyboardButton(text="📋 Подписка", callback_data=CallbackAction.MY_SUBSCRIPTION),
                InlineKeyboardButton(text="🔄 Продлить", callback_data=VpnCallback(action=VpnAction.RENEW).pack()),
            ],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton(
                    text="🚀 Подключить VPN",
                    callback_data=VpnCallback(action=VpnAction.NEW).pack(),
                ),
            ],
        ]

    rows.append([
        InlineKeyboardButton(text="📖 Инструкция", callback_data=CallbackAction.INSTRUCTION),
        InlineKeyboardButton(text="👫 Друзья", callback_data=CallbackAction.FRIENDS),
    ])
    rows.append([
        InlineKeyboardButton(text="🌐 Кабинет", callback_data=CallbackAction.CABINET),
        InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{app_config.bot.admin_username}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_keyboard_hwid_devices(devices: list[dict]) -> InlineKeyboardMarkup:
    """Список HWID-устройств с кнопками удаления."""
    rows = []
    for device in devices:
        model = device.get("device_model") or "Устройство"
        platform = device.get("platform") or ""
        label = f"{model} ({platform})" if platform else model
        rows.append([
            InlineKeyboardButton(text=f"❌ {label}", callback_data=f"hwid_del:{device['hwid']}"),
        ])
    rows.append([
        InlineKeyboardButton(text="🗑 Удалить все устройства", callback_data=CallbackAction.HWID_DELETE_ALL),
    ])
    rows.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackAction.MY_SUBSCRIPTION),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_keyboard_confirm_delete_all() -> InlineKeyboardMarkup:
    """Подтверждение удаления всех устройств."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить все", callback_data=CallbackAction.HWID_DELETE_ALL_CONFIRM),
            InlineKeyboardButton(text="Отмена", callback_data=CallbackAction.HWID_DEVICES),
        ],
    ])


def get_keyboard_subscription(is_expiring: bool = False) -> InlineKeyboardMarkup:
    """Кнопки на экране 'Моя подписка'."""
    if is_expiring:
        rows = [
            [InlineKeyboardButton(
                text="🔄 Продлить подписку",
                callback_data=VpnCallback(action=VpnAction.RENEW).pack(),
            )],
            [InlineKeyboardButton(text="📱 Мои устройства", callback_data=CallbackAction.HWID_DEVICES)],
            [
                InlineKeyboardButton(text="📖 Инструкция", callback_data=CallbackAction.INSTRUCTION),
                InlineKeyboardButton(text="🏠 Меню", callback_data=CallbackAction.START),
            ],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton(
                    text="🔄 Продлить",
                    callback_data=VpnCallback(action=VpnAction.RENEW).pack(),
                ),
                InlineKeyboardButton(text="📖 Инструкция", callback_data=CallbackAction.INSTRUCTION),
            ],
            [InlineKeyboardButton(text="📱 Мои устройства", callback_data=CallbackAction.HWID_DEVICES)],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackAction.START)],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_keyboard_device_count(
    action: str, referral_id: int | None = None
) -> InlineKeyboardMarkup:
    """Шаг 1: выбор количества устройств. 3 устройства выделены как хит."""
    labels = {1: "📱 1 устройство", 2: "📱📱 2 устройства", 3: "📱📱📱 3 устройства — ⭐ хит"}
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for count in (1, 2, 3):
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=labels[count],
                callback_data=VpnCallback(
                    action=action,
                    device_limit=count,
                    duration=0,
                    referral_id=referral_id,
                ).pack(),
            )
        ])
    return keyboard


def get_keyboard_tariff(
    action: str,
    device_limit: int = 1,
    referral_id: int | None = None,
) -> InlineKeyboardMarkup:
    """Шаг 2: выбор тарифа. 3 мес = хит, 6 мес = выгодно."""
    prices = TARIFF_MATRIX[device_limit]
    month_price = prices[1]

    badges = {3: " ⭐ хит", 6: " 💰 выгодно"}
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for months, label in [(1, "1 мес"), (3, "3 мес"), (6, "6 мес"), (12, "12 мес")]:
        price = prices[months]
        discount = round((1 - price / (month_price * months)) * 100)
        discount_text = f" (-{discount}%)" if discount > 0 else ""
        badge = badges.get(months, "")
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{label} — {price}₽{discount_text}{badge}",
                callback_data=VpnCallback(
                    action=action,
                    device_limit=device_limit,
                    duration=months,
                    referral_id=referral_id,
                    payment=price,
                ).pack(),
            )
        ])
    return keyboard


def get_keyboard_confirm_payment(
    action: str,
    device_limit: int,
    duration: int,
    payment: int,
    balance: int,
    referral_id: int | None = None,
) -> InlineKeyboardMarkup:
    """Шаг 3: подтверждение оплаты."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Оплатить",
                callback_data=VpnCallback(
                    action=action,
                    device_limit=device_limit,
                    duration=duration,
                    referral_id=referral_id,
                    payment=payment,
                    balance=balance,
                    choice=ChoiceType.YES,
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=VpnCallback(
                    action=action,
                    device_limit=device_limit,
                    duration=duration,
                    referral_id=referral_id,
                    payment=payment,
                    balance=balance,
                    choice=ChoiceType.NO,
                ).pack(),
            ),
        ]
    ])


def get_keyboard_instruction_platforms() -> InlineKeyboardMarkup:
    """Выбор платформы для инструкции."""
    platforms = [
        ("📱 Android", "android_phone"),
        ("🍏 iPhone / iPad", "ios"),
        ("💻 Windows", "windows"),
        ("💻 MacOS", "macos"),
        ("📺 Android TV", "tv"),
    ]
    rows = [
        [InlineKeyboardButton(text=label, callback_data=SettingsCallback(platform=code).pack())]
        for label, code in platforms
    ]
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackAction.START)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_keyboard_instruction_detail() -> InlineKeyboardMarkup:
    """Кнопки после инструкции — ключ, назад, меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мой ключ подписки", callback_data=CallbackAction.MY_SUBSCRIPTION)],
        [InlineKeyboardButton(text="◀️ Выбор платформы", callback_data=CallbackAction.INSTRUCTION)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackAction.START)],
    ])


def get_keyboard_friends(referral_code: str) -> InlineKeyboardMarkup:
    """Кнопки реферального экрана."""
    bot_name = app_config.bot.bot_name
    share_text = f"Попробуй VPN — 5 дней бесплатно! https://t.me/{bot_name}?start={referral_code}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться в Telegram", switch_inline_query=share_text)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackAction.START)],
    ])


def get_keyboard_referral_activate(referral_id: int) -> InlineKeyboardMarkup:
    """Экран реферальной активации — одна кнопка."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎁 Активировать бесплатный период",
                callback_data=VpnCallback(
                    action=VpnAction.REFERRAL,
                    referral_id=referral_id,
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data=CallbackAction.START,
            )
        ],
    ])


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
    """Клавиатура после получения VPN-ключа: скачать Happ + главное меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📥 Скачать Happ",
                callback_data=CallbackAction.INSTRUCTION,
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


def get_keyboard_migrate() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🔑 Получить новый ключ",
                callback_data=VpnCallback(action=VpnAction.MIGRATE).pack(),
            )
        ]]
    )
