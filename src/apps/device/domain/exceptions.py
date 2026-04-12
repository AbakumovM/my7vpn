class DeviceNotFound(Exception):
    def __init__(self, device_id: int | None = None, device_name: str | None = None) -> None:
        identifier = f"id={device_id}" if device_id is not None else f"name='{device_name}'"
        super().__init__(f"Device {identifier} not found")


class SubscriptionNotFound(Exception):
    def __init__(self, device_id: int) -> None:
        super().__init__(f"Subscription for device {device_id} not found")
        self.device_id = device_id


class UserDeviceNotFound(Exception):
    def __init__(self, telegram_id: int) -> None:
        super().__init__(f"No user found for telegram_id={telegram_id}")
        self.telegram_id = telegram_id


class PendingPaymentNotFound(Exception):
    def __init__(self, pending_id: int) -> None:
        super().__init__(f"PendingPayment id={pending_id} not found")
        self.pending_id = pending_id
