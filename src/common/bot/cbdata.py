from aiogram.filters.callback_data import CallbackData

from src.common.bot.keyboards.user_actions import ChoiceType, VpnAction


class VpnCallback(CallbackData, prefix="vpn"):
    action: VpnAction | None = None  # "new", "renew", "referral"
    device: str | None = None  # "ios", "android", "tv", "mac", "win"
    device_name: str | None = None  # Название устройства
    device_limit: int | None = None  # 1, 2 или 3 — выбирается на шаге 1.5
    duration: int | None = 0  # 1, 3, 6, 12 (месяцев)
    referral_id: int | None = None  # опционально, для рефералов
    payment: int | None = None  # сумма платежа
    balance: int | None = None  # остаток баланса пользователя
    choice: ChoiceType | None = None


class SettingsCallback(CallbackData, prefix="settings"):
    platform: str
