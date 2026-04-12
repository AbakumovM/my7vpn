import random
from dataclasses import dataclass
from datetime import UTC, datetime

from dateutil.relativedelta import relativedelta

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.view import ExpiringSubscriptionInfo
from src.apps.device.domain.commands import (
    ConfirmPayment,
    CreateDevice,
    CreateDeviceFree,
    CreatePendingPayment,
    DeleteDevice,
    GetExpiringSubscriptions,
    RejectPayment,
    RenewSubscription,
)
from src.apps.device.domain.exceptions import (
    DeviceNotFound,
    PendingPaymentNotFound,
    SubscriptionNotFound,
    UserDeviceNotFound,
)
from src.apps.device.domain.models import Device, Payment, PendingPayment, Subscription
from src.apps.user.application.interfaces.gateway import UserGateway
from src.apps.user.domain.exceptions import InsufficientBalance
from src.infrastructure.database.uow import SQLAlchemyUoW
from src.infrastructure.xui.client import XuiClient


@dataclass(frozen=True)
class DeviceCreatedInfo:
    device_name: str
    user_telegram_id: int


@dataclass(frozen=True)
class SubscriptionInfo:
    device_name: str
    end_date: datetime
    plan: int


@dataclass(frozen=True)
class PendingPaymentInfo:
    id: int
    user_telegram_id: int
    action: str
    device_type: str
    device_name: str | None
    duration: int
    amount: int


@dataclass(frozen=True)
class ConfirmPaymentResult:
    user_telegram_id: int
    device_name: str
    action: str              # "new" | "renew"
    vless_link: str | None   # None для renew
    end_date: datetime | None


class DeviceInteractor:
    def __init__(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        pending_gateway: PendingPaymentGateway,
        xui_client: XuiClient,
    ) -> None:
        self._gateway = gateway
        self._user_gateway = user_gateway
        self._uow = uow
        self._pending_gateway = pending_gateway
        self._xui_client = xui_client

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
            vpn_config=cmd.vpn_config,
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
            if renewal_user is None:
                raise UserDeviceNotFound(device.user_id)
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

    async def create_pending_payment(self, cmd: CreatePendingPayment) -> PendingPaymentInfo:
        now = datetime.now(UTC)
        pending = PendingPayment(
            user_telegram_id=cmd.user_telegram_id,
            action=cmd.action,
            device_type=cmd.device_type,
            device_name=cmd.device_name,
            duration=cmd.duration,
            amount=cmd.amount,
            balance_to_deduct=cmd.balance_to_deduct,
            created_at=now,
        )
        saved = await self._pending_gateway.save(pending)
        await self._uow.commit()
        return PendingPaymentInfo(
            id=saved.id,  # type: ignore[arg-type]
            user_telegram_id=saved.user_telegram_id,
            action=saved.action,
            device_type=saved.device_type,
            device_name=saved.device_name,
            duration=saved.duration,
            amount=saved.amount,
        )

    async def confirm_payment(self, cmd: ConfirmPayment) -> ConfirmPaymentResult:
        pending = await self._pending_gateway.get_by_id(cmd.pending_id)
        if pending is None:
            raise PendingPaymentNotFound(cmd.pending_id)

        vless_link: str | None = None
        device_name: str
        end_date: datetime | None = None

        if pending.action == "new":
            device_name = await self._generate_device_name(pending.device_type)
            vless_link = await self._xui_client.add_client(device_name)
            result = await self.create_device(
                CreateDevice(
                    telegram_id=pending.user_telegram_id,
                    device_type=pending.device_type,
                    period_months=pending.duration,
                    amount=pending.amount,
                    balance_to_deduct=pending.balance_to_deduct,
                    vpn_config=vless_link,
                )
            )
            # create_device already committed. Delete pending and commit again.
            device_name = result.device_name
        elif pending.action == "renew":
            if pending.device_name is None:
                raise DeviceNotFound(device_name="(None)")
            result_renew = await self.renew_subscription(
                RenewSubscription(
                    device_name=pending.device_name,
                    period_months=pending.duration,
                    amount=pending.amount,
                    balance_to_deduct=pending.balance_to_deduct,
                )
            )
            device_name = result_renew.device_name
            end_date = result_renew.end_date
        else:
            raise ValueError(f"Unknown pending action: {pending.action}")

        await self._pending_gateway.delete(cmd.pending_id)
        await self._uow.commit()

        return ConfirmPaymentResult(
            user_telegram_id=pending.user_telegram_id,
            device_name=device_name,
            action=pending.action,
            vless_link=vless_link,
            end_date=end_date,
        )

    async def reject_payment(self, cmd: RejectPayment) -> PendingPaymentInfo:
        pending = await self._pending_gateway.get_by_id(cmd.pending_id)
        if pending is None:
            raise PendingPaymentNotFound(cmd.pending_id)
        info = PendingPaymentInfo(
            id=pending.id,  # type: ignore[arg-type]
            user_telegram_id=pending.user_telegram_id,
            action=pending.action,
            device_type=pending.device_type,
            device_name=pending.device_name,
            duration=pending.duration,
            amount=pending.amount,
        )
        await self._pending_gateway.delete(cmd.pending_id)
        await self._uow.commit()
        return info

    async def _generate_device_name(self, device_type: str) -> str:
        seq = await self._gateway.get_next_seq()
        suffix = f"{seq}{random.randint(1, 5000)}"
        return f"{device_type} {suffix}"
