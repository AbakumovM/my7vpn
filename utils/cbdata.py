from typing import Optional
from aiogram.filters.callback_data import CallbackData

from keyboards.user_actions import ChoiceType, DeviceType, PaymentStatus, VpnAction


class VpnCallback(CallbackData, prefix="vpn"):
    action: Optional[VpnAction] = None  # "new", "renew", "referral"
    device: Optional[str] = None  # "ios", "android", "tv", "mac", "win"
    device_name: Optional[str] = None  # Название устройства
    duration: Optional[int] = 0  # 1, 3, 6, 12 (месяцев)
    referral_id: Optional[int] = None  # опционально, для рефералов
    payment: Optional[int] = None  # сумма платежа
    balance: Optional[int] = None  # остаток баланса пользователя
    choice: Optional[ChoiceType] = None
    payment_status: Optional[PaymentStatus] = None
