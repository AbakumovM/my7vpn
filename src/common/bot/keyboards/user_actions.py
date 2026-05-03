from enum import StrEnum


class CallbackAction(StrEnum):
    # Навигация
    START = "start"
    MY_SUBSCRIPTION = "my_subscription"
    INSTRUCTION = "instruction"
    FRIENDS = "friends"

    # Подтверждение
    YES = "yes"
    NO = "no"

    # Оплата
    PAYMENT_SUCCESS = "payment_success"
    CANCEL = "cancel"
    RENEW_SUB = "renew"
    NEW_SUB = "new"

    # HWID-устройства
    HWID_DEVICES = "hwid_devices"
    HWID_DELETE_ALL = "hwid_del_all"
    HWID_DELETE_ALL_CONFIRM = "hwid_del_all_yes"

    # Веб-кабинет
    CABINET = "cabinet"


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
    MIGRATE = "migrate"


class ChoiceType(StrEnum):
    YES = "yes"
    NO = "no"


# Цены по матрице (device_limit, months) → цена в рублях
TARIFF_MATRIX: dict[int, dict[int, int]] = {
    1: {1: 150,  3: 400,  6: 700,  12: 1200},
    2: {1: 250,  3: 650,  6: 1100, 12: 1900},
    3: {1: 350,  3: 900,  6: 1500, 12: 2600},
}
