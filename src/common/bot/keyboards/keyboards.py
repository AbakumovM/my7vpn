from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.common.bot.cbdata import (
    AdminConfirmCallback,
    SettingsCallback,
    VpnCallback,
)
from src.common.bot.keyboards.user_actions import (
    CallbackAction,
    ChoiceType,
    PaymentStatus,
    TARIFF_MATRIX,
    VpnAction,
)
from src.common.bot.lexicon.lexicon import LEXICON_INLINE_RU
from src.infrastructure.config import app_config


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
        InlineKeyboardButton(text="🌐 Кабинет", url=app_config.auth.site_url),
        InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{app_config.bot.admin_username}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_keyboard_subscription(is_expiring: bool = False) -> InlineKeyboardMarkup:
    """Кнопки на экране 'Моя подписка'."""
    if is_expiring:
        rows = [
            [InlineKeyboardButton(
                text="🔄 Продлить подписку",
                callback_data=VpnCallback(action=VpnAction.RENEW).pack(),
            )],
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
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackAction.START)],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_keyboard_device_count(
    action: str, referral_id: int | None = None
) -> InlineKeyboardMarkup:
    """Шаг 1: выбор количества устройств. 3 устройства выделены как хит."""
    labels = {1: "📱 1 устройство", 2: "📱📱 2 устройства", 3: "⭐ 📱📱📱 3 устройства — хит"}
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
    share_text = f"Попробуй VPN — 7 дней бесплатно! https://t.me/{bot_name}?start={referral_code}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться в Telegram", switch_inline_query=share_text)],
        [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data=f"copy_ref:{referral_code}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackAction.START)],
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
    """Клавиатура после получения VPN-ключа: инструкция + главное меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📖 Инструкция по подключению",
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
