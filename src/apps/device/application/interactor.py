import random
from dataclasses import dataclass
from datetime import UTC, datetime

from dateutil.relativedelta import relativedelta

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.view import ExpiringSubscriptionInfo
from src.apps.device.domain.commands import (
    CreateDevice,
    CreateDeviceFree,
    DeleteDevice,
    GetExpiringSubscriptions,
    RenewSubscription,
)
from src.apps.device.domain.exceptions import (
    DeviceNotFound,
    SubscriptionNotFound,
    UserDeviceNotFound,
)
from src.apps.device.domain.models import Device, Payment, Subscription
from src.apps.user.application.interfaces.gateway import UserGateway
from src.apps.user.domain.exceptions import InsufficientBalance
from src.infrastructure.database.uow import SQLAlchemyUoW


@dataclass(frozen=True)
class DeviceCreatedInfo:
    device_name: str
    user_telegram_id: int


@dataclass(frozen=True)
class SubscriptionInfo:
    device_name: str
    end_date: datetime
    plan: int


class DeviceInteractor:
    def __init__(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
    ) -> None:
        self._gateway = gateway
        self._user_gateway = user_gateway
        self._uow = uow

    async def create_device(self, cmd: CreateDevice) -> DeviceCreatedInfo:
        user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserDeviceNotFound(cmd.telegram_id)

        device_name = await self._generate_device_name(cmd.device_type)
        now = datetime.now(UTC)
        end_date = now + relativedelta(months=cmd.period_months)

        subscription = Subscription(
            device_id=0,  # заполнится после flush в gateway.save
            plan=cmd.period_months,
            start_date=now,
            end_date=end_date,
        )
        payment = Payment(
            subscription_id=0,  # заполнится после flush
            amount=cmd.amount,
            payment_date=now,
        )
        subscription_with_payment = subscription
        device = Device(
            user_id=user.telegram_id,
            device_name=device_name,
            created_at=now,
            subscription=subscription_with_payment,
        )
        # Прикрепляем платёж к подписке (gateway обработает)
        device.subscription.payments = [payment]  # type: ignore[attr-defined]

        if cmd.balance_to_deduct > 0:
            if user.balance < cmd.balance_to_deduct:
                raise InsufficientBalance(cmd.telegram_id, user.balance, cmd.balance_to_deduct)
            user.balance -= cmd.balance_to_deduct
            await self._user_gateway.save(user)

        await self._gateway.save(device)
        await self._uow.commit()
        return DeviceCreatedInfo(device_name=device_name, user_telegram_id=cmd.telegram_id)

    async def create_device_free(self, cmd: CreateDeviceFree) -> DeviceCreatedInfo:
        user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserDeviceNotFound(cmd.telegram_id)

        device_name = await self._generate_device_name(cmd.device_type)
        now = datetime.now(UTC)
        end_date = now + relativedelta(days=cmd.period_days)

        subscription = Subscription(
            device_id=0,
            plan=cmd.period_days,
            start_date=now,
            end_date=end_date,
        )
        subscription.payments = [Payment(subscription_id=0, amount=0, payment_date=now)]  # type: ignore[attr-defined]
        device = Device(
            user_id=user.telegram_id,
            device_name=device_name,
            created_at=now,
            subscription=subscription,
        )

        await self._gateway.save(device)
        await self._uow.commit()
        return DeviceCreatedInfo(device_name=device_name, user_telegram_id=cmd.telegram_id)

    async def delete_device(self, cmd: DeleteDevice) -> str:
        device = await self._gateway.get_by_id(cmd.device_id)
        if device is None:
            raise DeviceNotFound(device_id=cmd.device_id)

        device_name = device.device_name
        await self._gateway.delete(device)
        await self._uow.commit()
        return device_name

    async def renew_subscription(self, cmd: RenewSubscription) -> SubscriptionInfo:
        device = await self._gateway.get_by_name(cmd.device_name)
        if device is None:
            raise DeviceNotFound(device_name=cmd.device_name)
        if device.subscription is None:
            raise SubscriptionNotFound(device.id or 0)

        now = datetime.now(UTC)
        sub = device.subscription
        # Если подписка истекла — продлеваем от now, иначе — от end_date
        base = sub.end_date if sub.end_date > now else now
        sub.end_date = base + relativedelta(months=cmd.period_months)
        sub.plan = cmd.period_months
        sub.start_date = now

        if cmd.balance_to_deduct > 0:
            renewal_user = await self._user_gateway.get_by_telegram_id(device.user_id)
            if renewal_user is not None:
                if renewal_user.balance < cmd.balance_to_deduct:
                    raise InsufficientBalance(device.user_id, renewal_user.balance, cmd.balance_to_deduct)
                renewal_user.balance -= cmd.balance_to_deduct
                await self._user_gateway.save(renewal_user)

        await self._gateway.save(device)
        await self._uow.commit()
        return SubscriptionInfo(
            device_name=device.device_name,
            end_date=sub.end_date,
            plan=sub.plan,
        )

    async def get_expiring_subscriptions(
        self, cmd: GetExpiringSubscriptions
    ) -> list[ExpiringSubscriptionInfo]:
        # Делегируем в View (read-only), вызывается из контроллера планировщика
        # Этот метод здесь для единообразия API — реальная логика в DeviceView
        raise NotImplementedError("Use DeviceView.get_expiring_today() directly")

    async def _generate_device_name(self, device_type: str) -> str:
        seq = await self._gateway.get_next_seq()
        suffix = f"{seq}{random.randint(1, 5000)}"
        return f"{device_type} {suffix}"
