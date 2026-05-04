import random
from dataclasses import dataclass
from datetime import UTC, datetime

from dateutil.relativedelta import relativedelta

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
from src.apps.device.application.interfaces.subscription_gateway import SubscriptionGateway
from src.apps.device.domain.commands import (
    ConfirmPayment,
    CreateDevice,
    CreateDeviceFree,
    CreatePendingPayment,
    DeleteDevice,
    MigrateUser,
    RejectPayment,
    RenewSubscription,
)
from src.apps.device.domain.exceptions import (
    DeviceNotFound,
    PendingPaymentNotFound,
    RemnawaveUserNotFound,
    SubscriptionNotFound,
    UserDeviceNotFound,
)
from src.apps.device.domain.models import (
    Device,
    Payment,
    PendingPayment,
    Subscription,
    UserPayment,
    UserSubscription,
)
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
    action: str  # "new" | "renew"
    subscription_url: str | None
    end_date: datetime
    amount: int = 0
    duration: int = 0
    device_limit: int = 1
    referrer_telegram_id: int | None = None


@dataclass(frozen=True)
class FreeSubscriptionInfo:
    user_telegram_id: int
    subscription_url: str
    end_date: datetime


@dataclass(frozen=True)
class MigrateUserResult:
    subscription_url: str
    end_date: datetime


class DeviceInteractor:
    def __init__(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        pending_gateway: PendingPaymentGateway,
        remnawave_gateway: RemnawaveGateway,
        subscription_gateway: SubscriptionGateway,
    ) -> None:
        self._gateway = gateway
        self._user_gateway = user_gateway
        self._uow = uow
        self._pending_gateway = pending_gateway
        self._remnawave_gateway = remnawave_gateway
        self._subscription_gateway = subscription_gateway

    async def create_device(self, cmd: CreateDevice) -> DeviceCreatedInfo:
        user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserDeviceNotFound(cmd.telegram_id)

        device_name = await self._generate_device_name(cmd.device_type)
        now = datetime.now(UTC)
        end_date = now + relativedelta(months=cmd.period_months)

        subscription = Subscription(
            device_id=0,
            plan=cmd.period_months,
            start_date=now,
            end_date=end_date,
        )
        payment = Payment(
            subscription_id=0,
            amount=cmd.amount,
            payment_date=now,
        )
        device = Device(
            user_id=user.telegram_id,
            device_name=device_name,
            created_at=now,
            vpn_config=cmd.vpn_config,
            device_limit=cmd.device_limit,
            subscription=subscription,
        )
        device.subscription.payments = [payment]  # type: ignore[attr-defined]  # payments not declared in Subscription dataclass, set dynamically before ORM flush

        if cmd.balance_to_deduct > 0:
            if user.balance < cmd.balance_to_deduct:
                raise InsufficientBalance(cmd.telegram_id, user.balance, cmd.balance_to_deduct)
            user.balance -= cmd.balance_to_deduct
            await self._user_gateway.save(user)

        await self._gateway.save(device)
        await self._uow.commit()
        return DeviceCreatedInfo(device_name=device_name, user_telegram_id=cmd.telegram_id)

    async def create_device_free(self, cmd: CreateDeviceFree) -> FreeSubscriptionInfo:
        user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserDeviceNotFound(cmd.telegram_id)

        now = datetime.now(UTC)
        end_date = now + relativedelta(days=cmd.period_days)

        if user.remnawave_uuid is None:
            rw_info = await self._remnawave_gateway.create_user(
                telegram_id=cmd.telegram_id,
                expire_at=end_date,
                device_limit=cmd.device_limit,
            )
            user.remnawave_uuid = rw_info.uuid
            user.subscription_url = rw_info.subscription_url
        else:
            await self._remnawave_gateway.update_user(
                uuid=user.remnawave_uuid,
                expire_at=end_date,
                device_limit=cmd.device_limit,
            )
            if user.subscription_url is None:
                raise ValueError(
                    f"User {cmd.telegram_id} has remnawave_uuid but no subscription_url"
                )

        await self._user_gateway.save(user)

        user_sub = UserSubscription(
            user_telegram_id=cmd.telegram_id,
            plan=cmd.period_days,
            start_date=now,
            end_date=end_date,
            device_limit=cmd.device_limit,
        )
        user_sub = await self._subscription_gateway.save(user_sub)

        payment = UserPayment(
            user_telegram_id=cmd.telegram_id,
            subscription_id=user_sub.id,
            amount=0,
            duration=cmd.period_days,
            device_limit=cmd.device_limit,
            payment_method="реферал",
        )
        await self._subscription_gateway.save_payment(payment)
        await self._uow.commit()

        return FreeSubscriptionInfo(
            user_telegram_id=cmd.telegram_id,
            subscription_url=user.subscription_url,  # type: ignore[arg-type]  # set above or existed
            end_date=end_date,
        )

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
        base = sub.end_date if sub.end_date > now else now
        sub.end_date = base + relativedelta(months=cmd.period_months)
        sub.plan = cmd.period_months
        sub.start_date = now
        device.device_limit = cmd.device_limit

        if cmd.balance_to_deduct > 0:
            renewal_user = await self._user_gateway.get_by_telegram_id(device.user_id)
            if renewal_user is None:
                raise UserDeviceNotFound(device.user_id)
            if renewal_user.balance < cmd.balance_to_deduct:
                raise InsufficientBalance(
                    device.user_id, renewal_user.balance, cmd.balance_to_deduct
                )
            renewal_user.balance -= cmd.balance_to_deduct
            await self._user_gateway.save(renewal_user)

        await self._gateway.save(device)
        await self._uow.commit()
        return SubscriptionInfo(
            device_name=device.device_name,
            end_date=sub.end_date,
            plan=sub.plan,
        )

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
            device_limit=cmd.device_limit,
            created_at=now,
        )
        saved = await self._pending_gateway.save(pending)
        await self._uow.commit()
        return PendingPaymentInfo(
            id=saved.id,  # type: ignore[arg-type]  # id is set by ORM after save, always int at this point
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

        now = datetime.now(UTC)
        end_date: datetime
        user_sub: UserSubscription | None = None

        if pending.action == "new":
            end_date = now + relativedelta(months=pending.duration)
            user_sub = UserSubscription(
                user_telegram_id=pending.user_telegram_id,
                plan=pending.duration,
                start_date=now,
                end_date=end_date,
                device_limit=pending.device_limit,
            )
            user_sub = await self._subscription_gateway.save(user_sub)

        elif pending.action == "renew":
            # Новая модель: ищем UserSubscription по telegram_id
            user_sub = await self._subscription_gateway.get_active_by_telegram_id(
                pending.user_telegram_id
            )
            if user_sub is not None:
                base = user_sub.end_date if user_sub.end_date > now else now
                user_sub.end_date = base + relativedelta(months=pending.duration)
                user_sub.plan = pending.duration
                user_sub.device_limit = pending.device_limit
                user_sub = await self._subscription_gateway.save(user_sub)
                end_date = user_sub.end_date
            else:
                # Легаси: ищем Device по telegram_id (old device-based model)
                device = await self._gateway.get_active_by_telegram_id(pending.user_telegram_id)
                if device is None or device.subscription is None:
                    raise SubscriptionNotFound(0)
                sub = device.subscription
                base = sub.end_date if sub.end_date > now else now
                sub.end_date = base + relativedelta(months=pending.duration)
                sub.plan = pending.duration
                device.device_limit = pending.device_limit
                await self._gateway.save(device)
                end_date = sub.end_date
                # Создаём UserSubscription — миграция на новую модель
                user_sub = UserSubscription(
                    user_telegram_id=pending.user_telegram_id,
                    plan=pending.duration,
                    start_date=now,
                    end_date=end_date,
                    device_limit=pending.device_limit,
                )
                user_sub = await self._subscription_gateway.save(user_sub)
        else:
            raise ValueError(f"Unknown pending action: {pending.action}")

        # Считаем платные платежи до текущего (для определения первой оплаты)
        existing_paid_count = await self._subscription_gateway.count_payments_for_user(
            pending.user_telegram_id
        )

        # Сохраняем Payment
        payment = UserPayment(
            user_telegram_id=pending.user_telegram_id,
            subscription_id=user_sub.id,
            amount=pending.amount,
            duration=pending.duration,
            device_limit=pending.device_limit,
        )
        await self._subscription_gateway.save_payment(payment)

        # Получаем User + обрабатываем баланс и Remnawave
        user = await self._user_gateway.get_by_telegram_id(pending.user_telegram_id)
        if user is None:
            raise UserDeviceNotFound(pending.user_telegram_id)

        if pending.balance_to_deduct > 0:
            if user.balance < pending.balance_to_deduct:
                raise InsufficientBalance(
                    pending.user_telegram_id, user.balance, pending.balance_to_deduct
                )
            user.balance -= pending.balance_to_deduct

        if user.remnawave_uuid is None:
            rw_info = await self._remnawave_gateway.create_user(
                telegram_id=pending.user_telegram_id,
                expire_at=end_date,
                device_limit=pending.device_limit,
            )
            user.remnawave_uuid = rw_info.uuid
            user.subscription_url = rw_info.subscription_url
        else:
            try:
                await self._remnawave_gateway.update_user(
                    uuid=user.remnawave_uuid,
                    expire_at=end_date,
                    device_limit=pending.device_limit,
                )
            except RemnawaveUserNotFound:
                # User deleted from Remnawave — recreate and update local references
                rw_info = await self._remnawave_gateway.create_user(
                    telegram_id=pending.user_telegram_id,
                    expire_at=end_date,
                    device_limit=pending.device_limit,
                )
                user.remnawave_uuid = rw_info.uuid
                user.subscription_url = rw_info.subscription_url
            if user.subscription_url is None:
                raise ValueError(
                    f"User {pending.user_telegram_id} has remnawave_uuid but no subscription_url"
                )

        # Реферальный бонус — только при первой платной покупке
        referrer_telegram_id: int | None = None
        if existing_paid_count == 0 and user.referred_by is not None:
            referrer = await self._user_gateway.get_by_telegram_id(user.referred_by)
            if referrer is not None:
                referrer.balance += 50
                await self._user_gateway.save(referrer)
                referrer_telegram_id = referrer.telegram_id

        await self._user_gateway.save(user)
        await self._pending_gateway.delete(cmd.pending_id)
        await self._uow.commit()

        return ConfirmPaymentResult(
            user_telegram_id=pending.user_telegram_id,
            device_name="vpn",
            action=pending.action,
            subscription_url=user.subscription_url,
            end_date=end_date,
            amount=pending.amount,
            duration=pending.duration,
            device_limit=pending.device_limit,
            referrer_telegram_id=referrer_telegram_id,
        )

    async def _save_device(self, cmd: CreateDevice, device_name: str, end_date: datetime) -> None:
        user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserDeviceNotFound(cmd.telegram_id)

        now = datetime.now(UTC)
        subscription = Subscription(
            device_id=0, plan=cmd.period_months, start_date=now, end_date=end_date
        )
        subscription.payments = [Payment(subscription_id=0, amount=cmd.amount, payment_date=now)]  # type: ignore[attr-defined]  # payments not declared in Subscription dataclass, set dynamically before ORM flush
        device = Device(
            user_id=user.telegram_id,
            device_name=device_name,
            created_at=now,
            vpn_config=cmd.vpn_config,
            vpn_client_uuid=None,
            device_limit=cmd.device_limit,
            subscription=subscription,
        )

        if cmd.balance_to_deduct > 0:
            if user.balance < cmd.balance_to_deduct:
                raise InsufficientBalance(cmd.telegram_id, user.balance, cmd.balance_to_deduct)
            user.balance -= cmd.balance_to_deduct
            await self._user_gateway.save(user)

        await self._gateway.save(device)

    async def _save_renewal(self, cmd: RenewSubscription) -> SubscriptionInfo:
        device = await self._gateway.get_by_name(cmd.device_name)
        if device is None:
            raise DeviceNotFound(device_name=cmd.device_name)
        if device.subscription is None:
            raise SubscriptionNotFound(device.id or 0)

        now = datetime.now(UTC)
        sub = device.subscription
        base = sub.end_date if sub.end_date > now else now
        sub.end_date = base + relativedelta(months=cmd.period_months)
        sub.plan = cmd.period_months
        sub.start_date = now
        device.device_limit = cmd.device_limit

        if cmd.balance_to_deduct > 0:
            renewal_user = await self._user_gateway.get_by_telegram_id(device.user_id)
            if renewal_user is None:
                raise UserDeviceNotFound(device.user_id)
            if renewal_user.balance < cmd.balance_to_deduct:
                raise InsufficientBalance(
                    device.user_id, renewal_user.balance, cmd.balance_to_deduct
                )
            renewal_user.balance -= cmd.balance_to_deduct
            await self._user_gateway.save(renewal_user)

        await self._gateway.save(device)
        return SubscriptionInfo(
            device_name=device.device_name, end_date=sub.end_date, plan=sub.plan
        )

    async def reject_payment(self, cmd: RejectPayment) -> PendingPaymentInfo:
        pending = await self._pending_gateway.get_by_id(cmd.pending_id)
        if pending is None:
            raise PendingPaymentNotFound(cmd.pending_id)
        info = PendingPaymentInfo(
            id=pending.id,  # type: ignore[arg-type]  # id is set by ORM after gateway lookup, always int at this point
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

    async def migrate_user_to_remnawave(self, cmd: MigrateUser) -> MigrateUserResult:
        user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)
        if user is None:
            raise UserDeviceNotFound(cmd.telegram_id)

        # Идемпотентность: уже мигрирован
        if user.remnawave_uuid is not None:
            active_sub = await self._subscription_gateway.get_active_by_telegram_id(cmd.telegram_id)
            if active_sub is None:
                raise SubscriptionNotFound(telegram_id=cmd.telegram_id)
            return MigrateUserResult(
                subscription_url=user.subscription_url,  # type: ignore[arg-type]  # set during migration, always str when remnawave_uuid is set
                end_date=active_sub.end_date,
            )

        # Берём end_date из старой подписки
        end_date = await self._gateway.get_active_subscription_end_date(cmd.telegram_id)

        # Создаём Remnawave-аккаунт
        remnawave_user = await self._remnawave_gateway.create_user(
            telegram_id=cmd.telegram_id,
            expire_at=end_date,
            device_limit=1,
        )
        user.remnawave_uuid = remnawave_user.uuid
        user.subscription_url = remnawave_user.subscription_url

        # Создаём UserSubscription + UserPayment
        now_dt = datetime.now(UTC)
        subscription = UserSubscription(
            user_telegram_id=cmd.telegram_id,
            plan=(end_date - now_dt).days,
            start_date=now_dt,
            end_date=end_date,
            device_limit=1,
            is_active=True,
        )
        saved_sub = await self._subscription_gateway.save(subscription)
        payment = UserPayment(
            user_telegram_id=cmd.telegram_id,
            subscription_id=saved_sub.id,
            amount=0,
            duration=(end_date - now_dt).days,
            device_limit=1,
            payment_method="migration",
        )
        await self._subscription_gateway.save_payment(payment)
        await self._user_gateway.save(user)
        await self._uow.commit()

        return MigrateUserResult(
            subscription_url=user.subscription_url,  # type: ignore[arg-type]  # set above, always str at this point
            end_date=end_date,
        )

    async def _generate_device_name(self, device_type: str) -> str:
        seq = await self._gateway.get_next_seq()
        suffix = f"{seq}{random.randint(1, 5000)}"
        return f"{device_type} {suffix}"
