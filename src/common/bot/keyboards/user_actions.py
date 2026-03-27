from enum import IntEnum, StrEnum


class CallbackAction(StrEnum):
    # Помощь и ошибки
    VPN_ERROR = "vpn_error"
    SUPPORT_HELP = "support_help"

    # Устройства
    LIST_DEVICES = "list_devices"

    # Настройки
    SETTINGS_ANDROID_PHONE = "settings:android_phone"
    SETTINGS_IOS = "settings:ios"
    SETTINGS_DESKTOP = "settings:desktop"
    SETTINGS_TV = "settings:tv"

    # Навигация
    START = "start"
    INVITE = "invite"

    # Подтверждение действия
    YES = "yes"
    NO = "no"

    # Оплата
    PAYMENT_SUCCESS = "paymen_success"
    CANCEL = "cancel"
    RENEW_SUB = "renew"
    NEW_SUB = "new"

    # Ошибки с устройствами
    DEVICE_ERROR = "report:device_error"


class DeviceType(StrEnum):
    ANDROID_PHONE = "Android"
    IOS = "iOS"
    TV_ANDROID = "TV"
    COMPUTER_WINDOWS = "Windows"
    COMPUTER_MACOS = "MacOS"


class VpnAction(StrEnum):
    NEW = "new"
    RENEW = "renew"
    REFERRAL = "referral"


class ChoiceType(StrEnum):
    YES = "yes"
    NO = "no"
    STOP = "stop"


class ActualTariff(IntEnum):
    MONTH_1 = 150
    MONTH_3 = 400
    MONTH_6 = 700
    MONTH_12 = 1200


class PaymentStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
