from keyboards.user_actions import CallbackAction, DeviceType


LEXICON_COMMANDS_RU: dict[str, str] = {
    "start": "🏠 Главное меню",
    "devices": "📱 Мои устройства",
    "invite": "👩‍💻 Пригласить друга!",
    "help": "❓ Помощь",
}

LEXICON_INLINE_RU: dict[str, str] = {
    CallbackAction.VPN_ERROR: "☠️ Не работает VPN",
    CallbackAction.LIST_DEVICES: "Мои устройства 📱 💻",
    CallbackAction.SUPPORT_HELP: "Помощь 🆘 ",
    CallbackAction.SETTINGS_ANDROID_PHONE: "Настройки Android 📱",
    CallbackAction.SETTINGS_IOS: "Настройки iPhone 🍏",
    CallbackAction.SETTINGS_DESKTOP: "Настройки ПК 🖥(Windows, MacOS)",
    CallbackAction.SETTINGS_TV: "Настройки TV 📺 (Android)",
    CallbackAction.START: "🏠 Главное меню",
    CallbackAction.YES: "✅ Да, подтверждаю",
    CallbackAction.NO: "❌ Нет, передумал",
    CallbackAction.CANCEL: "❌ Отмена",
    CallbackAction.PAYMENT_SUCCESS: "✅ Я оплатил",
    CallbackAction.NEW_SUB: "✅ Я оплатил",
    CallbackAction.RENEW_SUB: "Продлить подписку 💳",
}

LEXICON_INLINE_DEVICE_RU: dict[str, str] = {
    DeviceType.ANDROID_PHONE: "📱 Android",
    DeviceType.IOS: "📱 iOS (iPhone, iPad)",
    DeviceType.TV_ANDROID: "📺 TV(Android)",
    DeviceType.COMPUTER_WINDOWS: "💻 Windows",
    DeviceType.COMPUTER_MACOS: "💻 MacOS",
}
