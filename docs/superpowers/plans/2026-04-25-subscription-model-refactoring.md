# Subscription Model Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать Device из flow покупки и продления — подписка привязывается к User напрямую; Payment хранится вечно; renew работает по telegram_id без device_name.

**Architecture:** Добавляем две новые таблицы (`user_subscriptions`, `user_payments`) и новый `SubscriptionGateway`. `confirm_payment` создаёт `UserSubscription` + `UserPayment` вместо `Device`. Renew ищет `UserSubscription` по `telegram_id`; если не нашёл — делает legacy-путь через `Device` и сразу создаёт `UserSubscription` (one-time migration). Старые таблицы `devices/subscriptions/payments` не трогаем — читаем только как fallback.

**Tech Stack:** Python 3.12, SQLAlchemy 2 async, Alembic, Aiogram 3, Dishka, pytest-asyncio

---

## Файловая структура

**Создать:**
- `src/apps/device/application/interfaces/subscription_gateway.py` — Protocol: `get_active_by_telegram_id`, `save`, `save_payment`
- `alembic/versions/XXXX_add_user_subscriptions_and_payments.py` — миграция

**Изменить:**
- `src/apps/device/adapters/orm.py` — добавить `UserSubscriptionORM`, `UserPaymentORM`
- `src/apps/device/domain/models.py` — добавить `UserSubscription`, `UserPayment`
- `src/apps/device/application/interfaces/gateway.py` — добавить `get_active_by_telegram_id`
- `src/apps/device/adapters/gateway.py` — реализовать `get_active_by_telegram_id` + `SQLAlchemySubscriptionGateway`
- `src/apps/device/application/interactor.py` — переписать `confirm_payment`, добавить `subscription_gateway`
- `src/apps/device/adapters/view.py` — `get_subscription_info` с fallback на новую таблицу
- `src/apps/device/ioc.py` — добавить `SubscriptionGateway` provider
- `tests/unit/device/conftest.py` — добавить `mock_subscription_gateway`
- `tests/unit/device/test_device_interactor.py` — обновить тесты `confirm_payment`

---

## Task 1: Новые ORM модели

**Files:**
- Modify: `src/apps/device/adapters/orm.py`

- [ ] **Step 1: Добавить UserSubscriptionORM и UserPaymentORM в orm.py**

Добавить в конец `src/apps/device/adapters/orm.py`:

```python
class UserSubscriptionORM(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan = Column(Integer, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    payments = relationship(
        "UserPaymentORM", back_populates="subscription", cascade="all, delete-orphan"
    )


class UserPaymentORM(Base):
    __tablename__ = "user_payments"

    id = Column(Integer, primary_key=True)
    user_telegram_id = Column(BigInteger, nullable=False, index=True)
    subscription_id = Column(
        Integer, ForeignKey("user_subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    amount = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False)
    device_limit = Column(Integer, nullable=False, default=1, server_default="1")
    payment_date = Column(DateTime(timezone=True), nullable=False)
    currency = Column(String, default="RUB")
    payment_method = Column(String, default="карта", nullable=True)
    status = Column(String(20), nullable=False, default="success", server_default="success")
    external_id = Column(String, nullable=True)

    subscription = relationship("UserSubscriptionORM", back_populates="payments")
```

- [ ] **Step 2: Проверить импорт**

```bash
uv run python -c "from src.apps.device.adapters.orm import UserSubscriptionORM, UserPaymentORM; print('OK')"
```

Ожидаемый вывод: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/apps/device/adapters/orm.py
git commit -m "feat: add UserSubscriptionORM and UserPaymentORM tables"
```

---

## Task 2: Новые доменные модели

**Files:**
- Modify: `src/apps/device/domain/models.py`

- [ ] **Step 1: Добавить UserSubscription и UserPayment в models.py**

Добавить в конец `src/apps/device/domain/models.py`:

```python
@dataclass
class UserSubscription:
    user_telegram_id: int
    plan: int
    start_date: datetime
    end_date: datetime
    device_limit: int = 1
    is_active: bool = True
    id: int | None = None


@dataclass
class UserPayment:
    user_telegram_id: int
    amount: int
    duration: int
    device_limit: int
    payment_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    subscription_id: int | None = None
    currency: str = "RUB"
    payment_method: str = "карта"
    status: str = "success"
    external_id: str | None = None
    id: int | None = None
```

- [ ] **Step 2: Проверить импорт**

```bash
uv run python -c "from src.apps.device.domain.models import UserSubscription, UserPayment; print('OK')"
```

Ожидаемый вывод: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/apps/device/domain/models.py
git commit -m "feat: add UserSubscription and UserPayment domain models"
```

---

## Task 3: SubscriptionGateway Protocol + реализация

**Files:**
- Create: `src/apps/device/application/interfaces/subscription_gateway.py`
- Modify: `src/apps/device/application/interfaces/gateway.py`
- Modify: `src/apps/device/adapters/gateway.py`

- [ ] **Step 1: Создать subscription_gateway.py**

Создать файл `src/apps/device/application/interfaces/subscription_gateway.py`:

```python
from typing import Protocol

from src.apps.device.domain.models import UserPayment, UserSubscription


class SubscriptionGateway(Protocol):
    async def get_active_by_telegram_id(self, telegram_id: int) -> UserSubscription | None: ...

    async def save(self, sub: UserSubscription) -> UserSubscription: ...

    async def save_payment(self, payment: UserPayment) -> UserPayment: ...
```

- [ ] **Step 2: Добавить get_active_by_telegram_id в DeviceGateway Protocol**

В `src/apps/device/application/interfaces/gateway.py` добавить метод:

```python
from typing import Protocol

from src.apps.device.domain.models import Device


class DeviceGateway(Protocol):
    async def get_by_id(self, device_id: int) -> Device | None: ...

    async def get_by_name(self, device_name: str) -> Device | None: ...

    async def get_active_by_telegram_id(self, telegram_id: int) -> Device | None: ...

    async def get_next_seq(self) -> int: ...

    async def save(self, device: Device) -> None: ...

    async def delete(self, device: Device) -> None: ...
```

- [ ] **Step 3: Реализовать get_active_by_telegram_id в SQLAlchemyDeviceGateway**

В `src/apps/device/adapters/gateway.py` добавить метод в класс `SQLAlchemyDeviceGateway` после `get_by_name`:

```python
async def get_active_by_telegram_id(self, telegram_id: int) -> Device | None:
    result = await self._session.execute(
        select(DeviceORM)
        .options(joinedload(DeviceORM.subscription).joinedload(SubscriptionORM.payments))
        .join(UserORM, DeviceORM.user_id == UserORM.id)
        .join(SubscriptionORM, DeviceORM.id == SubscriptionORM.device_id)
        .where(UserORM.telegram_id == telegram_id)
        .where(SubscriptionORM.is_active.is_(True))
        .order_by(SubscriptionORM.end_date.desc())
        .limit(1)
    )
    row = result.unique().scalar_one_or_none()
    return self._to_domain(row) if row else None
```

- [ ] **Step 4: Добавить SQLAlchemySubscriptionGateway в gateway.py**

В конец `src/apps/device/adapters/gateway.py` добавить:

```python
from src.apps.device.adapters.orm import UserPaymentORM, UserSubscriptionORM
from src.apps.device.domain.models import UserPayment, UserSubscription


class SQLAlchemySubscriptionGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_by_telegram_id(self, telegram_id: int) -> UserSubscription | None:
        result = await self._session.execute(
            select(UserSubscriptionORM)
            .join(UserORM, UserSubscriptionORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id)
            .where(UserSubscriptionORM.is_active.is_(True))
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UserSubscription(
            id=row.id,
            user_telegram_id=telegram_id,
            plan=row.plan,
            start_date=row.start_date,
            end_date=row.end_date,
            device_limit=row.device_limit,
            is_active=row.is_active,
        )

    async def save(self, sub: UserSubscription) -> UserSubscription:
        if sub.id is None:
            user_result = await self._session.execute(
                select(UserORM).where(UserORM.telegram_id == sub.user_telegram_id)
            )
            user_orm = user_result.scalar_one()
            orm = UserSubscriptionORM(
                user_id=user_orm.id,
                plan=sub.plan,
                start_date=sub.start_date,
                end_date=sub.end_date,
                device_limit=sub.device_limit,
                is_active=sub.is_active,
            )
            self._session.add(orm)
            await self._session.flush()
            sub.id = orm.id
        else:
            result = await self._session.execute(
                select(UserSubscriptionORM).where(UserSubscriptionORM.id == sub.id)
            )
            orm = result.scalar_one()
            orm.end_date = sub.end_date
            orm.device_limit = sub.device_limit
            orm.plan = sub.plan
            orm.start_date = sub.start_date
            await self._session.flush()
        return sub

    async def save_payment(self, payment: UserPayment) -> UserPayment:
        orm = UserPaymentORM(
            user_telegram_id=payment.user_telegram_id,
            subscription_id=payment.subscription_id,
            amount=payment.amount,
            duration=payment.duration,
            device_limit=payment.device_limit,
            payment_date=payment.payment_date,
            currency=payment.currency,
            payment_method=payment.payment_method,
            status=payment.status,
            external_id=payment.external_id,
        )
        self._session.add(orm)
        await self._session.flush()
        payment.id = orm.id  # type: ignore[misc]  # id set by ORM after flush
        return payment
```

Добавить импорты в начало `gateway.py` (в блок существующих импортов):

```python
from src.apps.device.adapters.orm import DeviceORM, PaymentORM, PendingPaymentORM, SubscriptionORM, UserPaymentORM, UserSubscriptionORM
from src.apps.device.domain.models import Device, PendingPayment, Subscription, UserPayment, UserSubscription
```

- [ ] **Step 5: Проверить импорты**

```bash
uv run python -c "
from src.apps.device.adapters.gateway import SQLAlchemySubscriptionGateway
from src.apps.device.application.interfaces.subscription_gateway import SubscriptionGateway
print('OK')
"
```

Ожидаемый вывод: `OK`

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/application/interfaces/subscription_gateway.py \
        src/apps/device/application/interfaces/gateway.py \
        src/apps/device/adapters/gateway.py
git commit -m "feat: add SubscriptionGateway protocol and SQLAlchemy implementation"
```

---

## Task 4: Alembic миграция

**Files:**
- Modify: `alembic/env.py` (если нужно добавить импорт новых ORM)
- Create: `alembic/versions/XXXX_add_user_subscriptions_and_payments.py`

- [ ] **Step 1: Убедиться что новые ORM импортируются в alembic/env.py**

Открыть `alembic/env.py`, найти импорты ORM моделей и убедиться что там есть строка, импортирующая `src.apps.device.adapters.orm` (обычно уже есть). Если нет — добавить:

```python
import src.apps.device.adapters.orm  # noqa: F401
import src.apps.user.adapters.orm    # noqa: F401
```

- [ ] **Step 2: Сгенерировать миграцию (требуется запущенная БД)**

```bash
uv run alembic revision --autogenerate -m "add user_subscriptions and user_payments"
```

Ожидаемый вывод: файл миграции создан, в нём `op.create_table('user_subscriptions', ...)` и `op.create_table('user_payments', ...)`.

- [ ] **Step 3: Проверить сгенерированную миграцию**

Открыть созданный файл в `alembic/versions/`. Убедиться:
- `user_subscriptions` содержит: `id`, `user_id` (FK→users), `plan`, `start_date`, `end_date`, `device_limit`, `is_active`
- `user_payments` содержит: `id`, `user_telegram_id`, `subscription_id` (nullable FK→user_subscriptions), `amount`, `duration`, `device_limit`, `payment_date`, `currency`, `payment_method`, `status`, `external_id`

- [ ] **Step 4: Применить миграцию**

```bash
uv run alembic upgrade head
```

Ожидаемый вывод: `Running upgrade ... -> XXXX, add user_subscriptions and user_payments`

- [ ] **Step 5: Commit**

```bash
git add alembic/
git commit -m "feat: migration — add user_subscriptions and user_payments tables"
```

---

## Task 5: Обновить interactor — confirm_payment

**Files:**
- Modify: `src/apps/device/application/interactor.py`

- [ ] **Step 1: Обновить импорты в interactor.py**

Заменить блок импортов в начале файла:

```python
import random
from dataclasses import dataclass
from datetime import UTC, datetime

from dateutil.relativedelta import relativedelta

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
from src.apps.device.application.interfaces.subscription_gateway import SubscriptionGateway
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
from src.apps.device.domain.models import Device, Payment, PendingPayment, Subscription, UserPayment, UserSubscription
from src.apps.user.application.interfaces.gateway import UserGateway
from src.apps.user.domain.exceptions import InsufficientBalance
from src.infrastructure.database.uow import SQLAlchemyUoW
```

- [ ] **Step 2: Добавить SubscriptionGateway в конструктор DeviceInteractor**

Найти `class DeviceInteractor` и заменить `__init__`:

```python
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
```

- [ ] **Step 3: Переписать confirm_payment**

Заменить весь метод `confirm_payment`:

```python
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
        await self._remnawave_gateway.update_user(
            uuid=user.remnawave_uuid,
            expire_at=end_date,
            device_limit=pending.device_limit,
        )
        if user.subscription_url is None:
            raise ValueError(
                f"User {pending.user_telegram_id} has remnawave_uuid but no subscription_url"
            )

    await self._user_gateway.save(user)
    await self._pending_gateway.delete(cmd.pending_id)
    await self._uow.commit()

    return ConfirmPaymentResult(
        user_telegram_id=pending.user_telegram_id,
        device_name="vpn",
        action=pending.action,
        subscription_url=user.subscription_url,
        end_date=end_date,
    )
```

- [ ] **Step 4: Проверить импорт**

```bash
uv run python -c "from src.apps.device.application.interactor import DeviceInteractor; print('OK')"
```

Ожидаемый вывод: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/apps/device/application/interactor.py
git commit -m "feat: confirm_payment creates UserSubscription+Payment directly, renew uses telegram_id"
```

---

## Task 6: Обновить View — get_subscription_info

**Files:**
- Modify: `src/apps/device/adapters/view.py`

- [ ] **Step 1: Обновить импорты в view.py**

В `src/apps/device/adapters/view.py` добавить в блок импортов:

```python
from src.apps.device.adapters.orm import DeviceORM, PaymentORM, SubscriptionORM, UserPaymentORM, UserSubscriptionORM
```

- [ ] **Step 2: Переписать get_subscription_info**

Найти метод `get_subscription_info` и полностью заменить его:

```python
async def get_subscription_info(self, telegram_id: int) -> SubscriptionInfo | None:
    # Сначала проверяем новую модель (user_subscriptions)
    new_result = await self._session.execute(
        select(
            UserSubscriptionORM.end_date,
            UserSubscriptionORM.device_limit,
        )
        .join(UserORM, UserSubscriptionORM.user_id == UserORM.id)
        .where(UserORM.telegram_id == telegram_id)
        .where(UserSubscriptionORM.is_active.is_(True))
        .order_by(UserSubscriptionORM.end_date.desc())
        .limit(1)
    )
    new_row = new_result.first()

    if new_row is not None:
        payment_result = await self._session.execute(
            select(UserPaymentORM.amount)
            .where(UserPaymentORM.user_telegram_id == telegram_id)
            .order_by(UserPaymentORM.payment_date.desc())
            .limit(1)
        )
        last_amount = payment_result.scalar_one_or_none()

        url_result = await self._session.execute(
            select(UserORM.subscription_url).where(UserORM.telegram_id == telegram_id)
        )
        subscription_url = url_result.scalar_one_or_none()

        return SubscriptionInfo(
            end_date=new_row.end_date,
            device_limit=new_row.device_limit,
            last_payment_amount=last_amount,
            subscription_url=subscription_url,
        )

    # Fallback: старая модель (devices → subscriptions)
    result = await self._session.execute(
        select(
            SubscriptionORM.end_date,
            DeviceORM.device_limit,
            UserORM.subscription_url,
        )
        .join(DeviceORM, SubscriptionORM.device_id == DeviceORM.id)
        .join(UserORM, DeviceORM.user_id == UserORM.id)
        .where(UserORM.telegram_id == telegram_id)
        .where(SubscriptionORM.is_active.is_(True))
        .order_by(SubscriptionORM.end_date.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None

    payment_result = await self._session.execute(
        select(PaymentORM.amount)
        .join(SubscriptionORM, PaymentORM.subscription_id == SubscriptionORM.id)
        .join(DeviceORM, SubscriptionORM.device_id == DeviceORM.id)
        .join(UserORM, DeviceORM.user_id == UserORM.id)
        .where(UserORM.telegram_id == telegram_id)
        .order_by(PaymentORM.payment_date.desc())
        .limit(1)
    )
    last_amount = payment_result.scalar_one_or_none()

    return SubscriptionInfo(
        end_date=row.end_date,
        device_limit=row.device_limit,
        last_payment_amount=last_amount,
        subscription_url=row.subscription_url,
    )
```

- [ ] **Step 3: Проверить импорт**

```bash
uv run python -c "from src.apps.device.adapters.view import SQLAlchemyDeviceView; print('OK')"
```

Ожидаемый вывод: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/apps/device/adapters/view.py
git commit -m "feat: get_subscription_info checks user_subscriptions first, falls back to legacy"
```

---

## Task 7: Обновить ioc.py

**Files:**
- Modify: `src/apps/device/ioc.py`

- [ ] **Step 1: Обновить ioc.py — добавить SubscriptionGateway**

Полное содержимое `src/apps/device/ioc.py`:

```python
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.gateway import (
    SQLAlchemyDeviceGateway,
    SQLAlchemyPendingPaymentGateway,
    SQLAlchemySubscriptionGateway,
)
from src.apps.device.adapters.remnawave_gateway import RemnawaveGatewayImpl
from src.apps.device.adapters.view import SQLAlchemyDeviceView
from src.apps.device.application.interactor import DeviceInteractor
from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
from src.apps.device.application.interfaces.subscription_gateway import SubscriptionGateway
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.user.application.interfaces.gateway import UserGateway
from src.infrastructure.config import AppConfig
from src.infrastructure.database.uow import SQLAlchemyUoW
from src.infrastructure.remnawave.client import RemnawaveClient


class DeviceProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_gateway(self, session: AsyncSession) -> DeviceGateway:
        return SQLAlchemyDeviceGateway(session)

    @provide
    def get_pending_gateway(self, session: AsyncSession) -> PendingPaymentGateway:
        return SQLAlchemyPendingPaymentGateway(session)

    @provide
    def get_subscription_gateway(self, session: AsyncSession) -> SubscriptionGateway:
        return SQLAlchemySubscriptionGateway(session)

    @provide
    def get_view(self, session: AsyncSession) -> DeviceView:
        return SQLAlchemyDeviceView(session)

    @provide(scope=Scope.APP)
    def get_remnawave_client(self, config: AppConfig) -> RemnawaveClient:
        return RemnawaveClient(config.remnawave)

    @provide
    def get_remnawave_gateway(self, client: RemnawaveClient) -> RemnawaveGateway:
        return RemnawaveGatewayImpl(client)

    @provide
    def get_interactor(
        self,
        gateway: DeviceGateway,
        user_gateway: UserGateway,
        uow: SQLAlchemyUoW,
        pending_gateway: PendingPaymentGateway,
        remnawave_gateway: RemnawaveGateway,
        subscription_gateway: SubscriptionGateway,
    ) -> DeviceInteractor:
        return DeviceInteractor(
            gateway=gateway,
            user_gateway=user_gateway,
            uow=uow,
            pending_gateway=pending_gateway,
            remnawave_gateway=remnawave_gateway,
            subscription_gateway=subscription_gateway,
        )
```

- [ ] **Step 2: Проверить импорт**

```bash
uv run python -c "from src.apps.device.ioc import DeviceProvider; print('OK')"
```

Ожидаемый вывод: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/apps/device/ioc.py
git commit -m "feat: add SubscriptionGateway to DeviceProvider DI"
```

---

## Task 8: Обновить тесты

**Files:**
- Modify: `tests/unit/device/conftest.py`
- Modify: `tests/unit/device/test_device_interactor.py`

- [ ] **Step 1: Обновить conftest.py — добавить mock_subscription_gateway**

Полное содержимое `tests/unit/device/conftest.py`:

```python
import pytest
from unittest.mock import AsyncMock

from src.apps.device.application.interfaces.gateway import DeviceGateway
from src.apps.device.application.interfaces.pending_gateway import PendingPaymentGateway
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
from src.apps.device.application.interfaces.subscription_gateway import SubscriptionGateway
from src.apps.device.application.interactor import DeviceInteractor
from src.apps.user.application.interfaces.gateway import UserGateway
from src.infrastructure.database.uow import SQLAlchemyUoW


@pytest.fixture
def mock_gateway() -> AsyncMock:
    return AsyncMock(spec=DeviceGateway)


@pytest.fixture
def mock_user_gateway() -> AsyncMock:
    return AsyncMock(spec=UserGateway)


@pytest.fixture
def mock_uow() -> AsyncMock:
    return AsyncMock(spec=SQLAlchemyUoW)


@pytest.fixture
def mock_pending_gateway() -> AsyncMock:
    return AsyncMock(spec=PendingPaymentGateway)


@pytest.fixture
def mock_remnawave_gateway() -> AsyncMock:
    return AsyncMock(spec=RemnawaveGateway)


@pytest.fixture
def mock_subscription_gateway() -> AsyncMock:
    return AsyncMock(spec=SubscriptionGateway)


@pytest.fixture
def interactor(
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_uow: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
    mock_subscription_gateway: AsyncMock,
) -> DeviceInteractor:
    return DeviceInteractor(
        gateway=mock_gateway,
        user_gateway=mock_user_gateway,
        uow=mock_uow,
        pending_gateway=mock_pending_gateway,
        remnawave_gateway=mock_remnawave_gateway,
        subscription_gateway=mock_subscription_gateway,
    )
```

- [ ] **Step 2: Запустить тесты — убедиться что текущие падают**

```bash
uv run pytest tests/unit/device/ -v --tb=short 2>&1 | tail -20
```

Ожидаемый вывод: ошибки в тестах `confirm_payment` — `mock_subscription_gateway` не настроен.

- [ ] **Step 3: Обновить test_confirm_payment_new_creates_device_and_returns_result**

Найти тест `test_confirm_payment_new_creates_device_and_returns_result` и заменить полностью:

```python
@pytest.mark.asyncio
async def test_confirm_payment_new_creates_subscription_and_returns_result(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
    mock_subscription_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    pending = PendingPayment(
        id=5,
        user_telegram_id=123,
        action="new",
        device_type="vpn",
        duration=1,
        amount=150,
        balance_to_deduct=0,
        device_limit=1,
        created_at=datetime.now(UTC),
    )
    mock_pending_gateway.get_by_id.return_value = pending
    saved_sub = UserSubscription(id=10, user_telegram_id=123, plan=1,
                                  start_date=datetime.now(UTC),
                                  end_date=datetime.now(UTC) + timedelta(days=30),
                                  device_limit=1)
    mock_subscription_gateway.save.return_value = saved_sub
    mock_user_gateway.get_by_telegram_id.return_value = User(
        telegram_id=123, balance=0, remnawave_uuid=None, subscription_url=None
    )
    mock_remnawave_gateway.create_user.return_value = _make_remnawave_user_info()

    result = await interactor.confirm_payment(ConfirmPayment(pending_id=5))

    mock_subscription_gateway.save.assert_called_once()
    mock_subscription_gateway.save_payment.assert_called_once()
    mock_gateway.save.assert_not_called()  # Device больше не создаётся
    mock_pending_gateway.delete.assert_called_once_with(5)
    mock_uow.commit.assert_called_once()
    assert result.action == "new"
    assert result.subscription_url == "https://sub.test/abc"
    assert result.user_telegram_id == 123
```

Добавить импорт `UserSubscription` в начало файла:

```python
from src.apps.device.domain.models import Device, PendingPayment, Subscription, UserSubscription
```

- [ ] **Step 4: Обновить тест renew для нового пользователя (UserSubscription найден)**

Найти `test_confirm_payment_renew_updates_remnawave_when_uuid_exists` и заменить:

```python
@pytest.mark.asyncio
async def test_confirm_payment_renew_updates_subscription_and_remnawave(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
    mock_subscription_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    """Продление нового пользователя: UserSubscription найден → update_user."""
    now = datetime.now(UTC)
    existing_sub = UserSubscription(
        id=20,
        user_telegram_id=123,
        plan=1,
        start_date=now - timedelta(days=20),
        end_date=now + timedelta(days=10),
        device_limit=1,
    )
    mock_subscription_gateway.get_active_by_telegram_id.return_value = existing_sub
    updated_sub = UserSubscription(
        id=20,
        user_telegram_id=123,
        plan=3,
        start_date=now,
        end_date=now + timedelta(days=100),
        device_limit=2,
    )
    mock_subscription_gateway.save.return_value = updated_sub
    pending = PendingPayment(
        id=8,
        user_telegram_id=123,
        action="renew",
        device_type="vpn",
        duration=3,
        amount=400,
        balance_to_deduct=0,
        device_limit=2,
        created_at=now,
    )
    mock_pending_gateway.get_by_id.return_value = pending
    user = User(
        telegram_id=123,
        balance=0,
        remnawave_uuid="rw-uuid",
        subscription_url="https://sub.test/url",
    )
    mock_user_gateway.get_by_telegram_id.return_value = user

    result = await interactor.confirm_payment(ConfirmPayment(pending_id=8))

    mock_remnawave_gateway.update_user.assert_called_once()
    mock_remnawave_gateway.create_user.assert_not_called()
    mock_gateway.save.assert_not_called()  # legacy Device не трогается
    call_kwargs = mock_remnawave_gateway.update_user.call_args.kwargs
    assert call_kwargs["uuid"] == "rw-uuid"
    assert call_kwargs["device_limit"] == 2
    assert result.subscription_url == "https://sub.test/url"
```

- [ ] **Step 5: Обновить тест renew для legacy пользователя (UserSubscription не найден)**

Найти `test_confirm_payment_renew_creates_remnawave_user_for_migration` и заменить:

```python
@pytest.mark.asyncio
async def test_confirm_payment_renew_legacy_user_migrates_to_new_model(
    interactor: DeviceInteractor,
    mock_gateway: AsyncMock,
    mock_user_gateway: AsyncMock,
    mock_pending_gateway: AsyncMock,
    mock_remnawave_gateway: AsyncMock,
    mock_subscription_gateway: AsyncMock,
    mock_uow: AsyncMock,
) -> None:
    """Legacy-пользователь продлевает: UserSubscription не найден → Device fallback + create_user + создаём UserSubscription."""
    mock_subscription_gateway.get_active_by_telegram_id.return_value = None

    sub = Subscription(
        device_id=1,
        plan=1,
        start_date=datetime.now(UTC),
        end_date=datetime.now(UTC) + timedelta(days=5),
    )
    device = Device(id=1, user_id=123, device_name="Android 1", subscription=sub)
    mock_gateway.get_active_by_telegram_id.return_value = device

    new_user_sub = UserSubscription(
        id=30,
        user_telegram_id=123,
        plan=1,
        start_date=datetime.now(UTC),
        end_date=datetime.now(UTC) + timedelta(days=35),
        device_limit=1,
    )
    mock_subscription_gateway.save.return_value = new_user_sub

    pending = PendingPayment(
        id=7,
        user_telegram_id=123,
        action="renew",
        device_type="vpn",
        duration=1,
        amount=150,
        balance_to_deduct=0,
        device_limit=1,
        created_at=datetime.now(UTC),
    )
    mock_pending_gateway.get_by_id.return_value = pending
    user = User(telegram_id=123, balance=0, remnawave_uuid=None, subscription_url=None)
    mock_user_gateway.get_by_telegram_id.return_value = user
    mock_remnawave_gateway.create_user.return_value = _make_remnawave_user_info(
        uuid="migrated-uuid", subscription_url="https://sub.test/migrated"
    )

    result = await interactor.confirm_payment(ConfirmPayment(pending_id=7))

    mock_gateway.get_active_by_telegram_id.assert_called_once_with(123)
    mock_gateway.save.assert_called_once()  # Device обновлён
    mock_subscription_gateway.save.assert_called_once()  # UserSubscription создан
    mock_subscription_gateway.save_payment.assert_called_once()
    mock_remnawave_gateway.create_user.assert_called_once()
    assert result.subscription_url == "https://sub.test/migrated"
```

- [ ] **Step 6: Обновить тесты confirm_payment_new для remnawave — добавить mock_subscription_gateway**

Найти `test_confirm_payment_new_creates_remnawave_user_when_no_uuid` и `test_confirm_payment_new_updates_remnawave_user_when_uuid_exists` — добавить в сигнатуру `mock_subscription_gateway: AsyncMock` и настроить:

Для обоих тестов добавить параметр и настройку:

```python
# Добавить параметр:
mock_subscription_gateway: AsyncMock,

# Добавить настройку (после mock_pending_gateway.get_by_id.return_value = pending):
saved_sub = UserSubscription(id=10, user_telegram_id=123, plan=1,
                              start_date=datetime.now(UTC),
                              end_date=datetime.now(UTC) + timedelta(days=30),
                              device_limit=1)
mock_subscription_gateway.save.return_value = saved_sub
```

- [ ] **Step 7: Запустить все тесты device**

```bash
uv run pytest tests/unit/device/ -v --tb=short
```

Ожидаемый вывод: все тесты `PASSED`.

- [ ] **Step 8: Запустить все unit-тесты**

```bash
uv run pytest tests/unit/ -v --tb=short 2>&1 | tail -15
```

Ожидаемый вывод: все device-тесты `PASSED`, 4 pre-existing падения в `user/` (не наша задача).

- [ ] **Step 9: Commit**

```bash
git add tests/unit/device/conftest.py tests/unit/device/test_device_interactor.py
git commit -m "test: update confirm_payment tests for subscription-based model"
```
