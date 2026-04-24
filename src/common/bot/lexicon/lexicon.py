from src.common.bot.keyboards.user_actions import CallbackAction, DeviceType

LEXICON_COMMANDS_RU: dict[str, str] = {
    "start": "🏠 Главное меню",
    "invite": "👫 Пригласить друга",
    "help": "📖 Инструкция",
}

LEXICON_INLINE_RU: dict[str, str] = {
    CallbackAction.MY_SUBSCRIPTION: "📋 Подписка",
    CallbackAction.RENEW_SUB: "🔄 Продлить",
    CallbackAction.INSTRUCTION: "📖 Инструкция",
    CallbackAction.FRIENDS: "👫 Друзья",
    CallbackAction.NEW_SUB: "🚀 Подключить VPN",
    CallbackAction.START: "🏠 Главное меню",
    CallbackAction.YES: "✅ Оплатить",
    CallbackAction.NO: "❌ Отмена",
    CallbackAction.CANCEL: "❌ Отмена",
    CallbackAction.PAYMENT_SUCCESS: "✅ Я оплатил",
}

LEXICON_INLINE_DEVICE_RU: dict[str, str] = {
    DeviceType.ANDROID_PHONE: "📱 Android",
    DeviceType.IOS: "🍏 iPhone / iPad",
    DeviceType.TV_ANDROID: "📺 Android TV",
    DeviceType.COMPUTER_WINDOWS: "💻 Windows",
    DeviceType.COMPUTER_MACOS: "💻 MacOS",
}
