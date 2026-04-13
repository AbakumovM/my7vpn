from typing import Literal

from aiogram.filters.callback_data import CallbackData

from src.common.bot.keyboards.user_actions import ChoiceType, PaymentStatus, VpnAction


class VpnCallback(CallbackData, prefix="vpn"):
    action: VpnAction | None = None  # "new", "renew", "referral"
    device: str | None = None  # "ios", "android", "tv", "mac", "win"
    device_name: str | None = None  # Название устройства
    duration: int | None = 0  # 1, 3, 6, 12 (месяцев)
    referral_id: int | None = None  # опционально, для рефералов
    payment: int | None = None  # сумма платежа
    balance: int | None = None  # остаток баланса пользователя
    choice: ChoiceType | None = None
    payment_status: PaymentStatus | None = None


class DeviceConfCallback(CallbackData, prefix="conf"):
    device_id: int


class DeviceDeleteCallback(CallbackData, prefix="appr_del_device"):
    device_id: int


class DeviceErrorCallback(CallbackData, prefix="report__device_error"):
    device_id: int


class SettingsCallback(CallbackData, prefix="settings"):
    platform: str


class AdminConfirmCallback(CallbackData, prefix="adm"):
    pending_id: int
    action: Literal["confirm", "reject"]
