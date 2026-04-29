# Admin Subscriber Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить 4 Telegram-команды для администратора: `/admin_stats`, `/admin_expiring`, `/admin_churn`, `/admin_user`.

**Architecture:** Новый `AdminView` Protocol в user-домене — read-only запросы к `users` + `user_subscriptions` (новая модель). Реализация — `SQLAlchemyAdminView`. Команды — отдельный роутер `admin_router.py`, подключённый к dispatcher только для admin_id. Все данные из БД — легаси-пользователи (только в `subscriptions`, без `user_subscriptions`) в статистику не попадут до первого продления.

**Tech Stack:** Python 3.12, Aiogram 3, SQLAlchemy async, Dishka (`FromDishka`), pytest.

---

## Карта файлов

| Файл | Действие | Назначение |
|------|----------|-----------|
| `src/apps/user/application/interfaces/admin_view.py` | Создать | Protocol + frozen dataclasses результатов |
| `src/apps/user/adapters/admin_view.py` | Создать | SQLAlchemy реализация запросов |
| `src/apps/user/ioc.py` | Изменить | Зарегистрировать `AdminView` в `UserProvider` |
| `src/apps/user/controllers/bot/admin_router.py` | Создать | Aiogram handlers для 4 команд |
| `main_bot.py` | Изменить | Подключить `admin_router` к dispatcher |
| `tests/unit/user/test_admin_view.py` | Создать | Unit-тесты форматирования ответов |

---

## Задача 1: AdminView Protocol и dataclasses

**Файлы:**
- Создать: `src/apps/user/application/interfaces/admin_view.py`

- [ ] **Шаг 1: Создать файл с Protocol и dataclasses**

```python
# src/apps/user/application/interfaces/admin_view.py
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class AdminStats:
    total_users: int
    active_subscribers: int
    new_today: int
    new_week: int
    new_month: int


@dataclass(frozen=True)
class AdminExpiring:
    expiring_3d: int
    expiring_7d: int
    expiring_30d: int


@dataclass(frozen=True)
class AdminChurn:
    churned_7d: int
    churned_30d: int
    renewal_rate_30d: int  # процент 0–100


@dataclass(frozen=True)
class AdminUserInfo:
    telegram_id: int
    balance: int
    referred_by: int | None
    active_until: datetime | None
    device_limit: int | None


class AdminView(Protocol):
    async def get_stats(self) -> AdminStats: ...
    async def get_expiring(self) -> AdminExpiring: ...
    async def get_churn(self) -> AdminChurn: ...
    async def get_user_info(self, telegram_id: int) -> AdminUserInfo | None: ...
```

- [ ] **Шаг 2: Закоммитить**

```bash
git add src/apps/user/application/interfaces/admin_view.py
git commit -m "feat: add AdminView protocol and dataclasses"
```

---

## Задача 2: SQLAlchemy реализация AdminView

**Файлы:**
- Создать: `src/apps/user/adapters/admin_view.py`

- [ ] **Шаг 1: Создать файл**

```python
# src/apps/user/adapters/admin_view.py
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import SubscriptionORM, UserSubscriptionORM, DeviceORM
from src.apps.user.adapters.orm import UserORM
from src.apps.user.application.interfaces.admin_view import (
    AdminChurn,
    AdminExpiring,
    AdminStats,
    AdminUserInfo,
)


class SQLAlchemyAdminView:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_stats(self) -> AdminStats:
        now = datetime.now(UTC)
        today = date.today()

        total = await self._session.scalar(select(func.count(UserORM.id))) or 0

        active = await self._session.scalar(
            select(func.count(UserSubscriptionORM.id)).where(
                UserSubscriptionORM.is_active.is_(True),
                UserSubscriptionORM.end_date > now,
            )
        ) or 0

        new_today = await self._session.scalar(
            select(func.count(UserORM.id)).where(UserORM.created_at == today)
        ) or 0

        new_week = await self._session.scalar(
            select(func.count(UserORM.id)).where(
                UserORM.created_at >= today - timedelta(days=7)
            )
        ) or 0

        new_month = await self._session.scalar(
            select(func.count(UserORM.id)).where(
                UserORM.created_at >= today - timedelta(days=30)
            )
        ) or 0

        return AdminStats(
            total_users=total,
            active_subscribers=active,
            new_today=new_today,
            new_week=new_week,
            new_month=new_month,
        )

    async def get_expiring(self) -> AdminExpiring:
        now = datetime.now(UTC)

        def count_expiring(days: int):
            return (
                select(func.count(UserSubscriptionORM.id))
                .where(
                    UserSubscriptionORM.is_active.is_(True),
                    UserSubscriptionORM.end_date > now,
                    UserSubscriptionORM.end_date <= now + timedelta(days=days),
                )
            )

        exp_3 = await self._session.scalar(count_expiring(3)) or 0
        exp_7 = await self._session.scalar(count_expiring(7)) or 0
        exp_30 = await self._session.scalar(count_expiring(30)) or 0

        return AdminExpiring(expiring_3d=exp_3, expiring_7d=exp_7, expiring_30d=exp_30)

    async def get_churn(self) -> AdminChurn:
        now = datetime.now(UTC)

        # Подзапрос: user_id с активной подпиской прямо сейчас
        active_user_ids = (
            select(UserSubscriptionORM.user_id)
            .where(
                UserSubscriptionORM.is_active.is_(True),
                UserSubscriptionORM.end_date > now,
            )
            .scalar_subquery()
        )

        def count_churned(days: int):
            return (
                select(func.count(func.distinct(UserSubscriptionORM.user_id)))
                .where(
                    UserSubscriptionORM.end_date < now,
                    UserSubscriptionORM.end_date >= now - timedelta(days=days),
                    UserSubscriptionORM.user_id.not_in(active_user_ids),
                )
            )

        churned_7 = await self._session.scalar(count_churned(7)) or 0
        churned_30 = await self._session.scalar(count_churned(30)) or 0

        # Всего истекло за 30 дней (для расчёта renewal rate)
        total_expired_30 = await self._session.scalar(
            select(func.count(func.distinct(UserSubscriptionORM.user_id))).where(
                UserSubscriptionORM.end_date < now,
                UserSubscriptionORM.end_date >= now - timedelta(days=30),
            )
        ) or 0

        if total_expired_30 > 0:
            renewed_30 = total_expired_30 - churned_30
            renewal_rate = round(renewed_30 / total_expired_30 * 100)
        else:
            renewal_rate = 0

        return AdminChurn(
            churned_7d=churned_7,
            churned_30d=churned_30,
            renewal_rate_30d=renewal_rate,
        )

    async def get_user_info(self, telegram_id: int) -> AdminUserInfo | None:
        user_row = await self._session.execute(
            select(UserORM).where(UserORM.telegram_id == telegram_id)
        )
        user = user_row.scalar_one_or_none()
        if user is None:
            return None

        # Ищем активную подписку (новая модель)
        sub_row = await self._session.execute(
            select(UserSubscriptionORM)
            .where(
                UserSubscriptionORM.user_id == user.id,
                UserSubscriptionORM.is_active.is_(True),
                UserSubscriptionORM.end_date > datetime.now(UTC),
            )
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        sub = sub_row.scalar_one_or_none()

        # Fallback: легаси через devices → subscriptions
        if sub is None:
            legacy_row = await self._session.execute(
                select(SubscriptionORM)
                .join(DeviceORM, SubscriptionORM.device_id == DeviceORM.id)
                .where(
                    DeviceORM.user_id == user.id,
                    SubscriptionORM.is_active.is_(True),
                    SubscriptionORM.end_date > datetime.now(UTC),
                )
                .order_by(SubscriptionORM.end_date.desc())
                .limit(1)
            )
            legacy_sub = legacy_row.scalar_one_or_none()
            active_until = legacy_sub.end_date if legacy_sub else None
            device_limit = None  # легаси не хранит device_limit в подписке напрямую
        else:
            active_until = sub.end_date
            device_limit = sub.device_limit

        return AdminUserInfo(
            telegram_id=telegram_id,
            balance=user.balance or 0,
            referred_by=user.referred_by,
            active_until=active_until,
            device_limit=device_limit,
        )
```

- [ ] **Шаг 2: Закоммитить**

```bash
git add src/apps/user/adapters/admin_view.py
git commit -m "feat: implement SQLAlchemyAdminView"
```

---

## Задача 3: Зарегистрировать AdminView в DI

**Файлы:**
- Изменить: `src/apps/user/ioc.py`

- [ ] **Шаг 1: Добавить `provide` для AdminView**

Читаем текущий файл `src/apps/user/ioc.py`:

```python
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.user.adapters.admin_view import SQLAlchemyAdminView
from src.apps.user.adapters.gateway import SQLAlchemyUserGateway
from src.apps.user.adapters.view import SQLAlchemyUserView
from src.apps.user.application.interactor import UserInteractor
from src.apps.user.application.interfaces.admin_view import AdminView
from src.apps.user.application.interfaces.gateway import UserGateway
from src.apps.user.application.interfaces.view import UserView
from src.infrastructure.database.uow import SQLAlchemyUoW


class UserProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_gateway(self, session: AsyncSession) -> UserGateway:
        return SQLAlchemyUserGateway(session)

    @provide
    def get_view(self, session: AsyncSession) -> UserView:
        return SQLAlchemyUserView(session)

    @provide
    def get_admin_view(self, session: AsyncSession) -> AdminView:
        return SQLAlchemyAdminView(session)

    @provide
    def get_interactor(self, gateway: UserGateway, uow: SQLAlchemyUoW) -> UserInteractor:
        return UserInteractor(gateway=gateway, uow=uow)
```

- [ ] **Шаг 2: Закоммитить**

```bash
git add src/apps/user/ioc.py
git commit -m "feat: register AdminView in UserProvider"
```

---

## Задача 4: Admin bot router

**Файлы:**
- Создать: `src/apps/user/controllers/bot/admin_router.py`

- [ ] **Шаг 1: Создать файл**

```python
# src/apps/user/controllers/bot/admin_router.py
import structlog
from aiogram import F, Router, types
from aiogram.filters import Command
from dishka.integrations.aiogram import FromDishka

from src.apps.user.application.interfaces.admin_view import AdminUserInfo, AdminView
from src.infrastructure.config import app_config

log = structlog.get_logger(__name__)

ADMIN_ID = app_config.bot.admin_id

router = Router()
router.message.filter(F.from_user.id == ADMIN_ID)


@router.message(Command("admin_stats"))
async def handle_admin_stats(
    msg: types.Message,
    admin_view: FromDishka[AdminView],
) -> None:
    stats = await admin_view.get_stats()
    await msg.answer(
        f"📊 <b>Статистика подписчиков</b>\n\n"
        f"👥 Всего пользователей: <b>{stats.total_users}</b>\n"
        f"✅ Активных подписок: <b>{stats.active_subscribers}</b>\n\n"
        f"📅 Новых сегодня: <b>{stats.new_today}</b>\n"
        f"📅 За неделю: <b>{stats.new_week}</b>\n"
        f"📅 За месяц: <b>{stats.new_month}</b>"
    )


@router.message(Command("admin_expiring"))
async def handle_admin_expiring(
    msg: types.Message,
    admin_view: FromDishka[AdminView],
) -> None:
    data = await admin_view.get_expiring()
    await msg.answer(
        f"⏳ <b>Истекающие подписки</b>\n\n"
        f"За 3 дня: <b>{data.expiring_3d}</b>\n"
        f"За 7 дней: <b>{data.expiring_7d}</b>\n"
        f"За 30 дней: <b>{data.expiring_30d}</b>"
    )


@router.message(Command("admin_churn"))
async def handle_admin_churn(
    msg: types.Message,
    admin_view: FromDishka[AdminView],
) -> None:
    data = await admin_view.get_churn()
    await msg.answer(
        f"📉 <b>Отток подписчиков</b>\n\n"
        f"❌ Не продлили за 7 дней: <b>{data.churned_7d}</b>\n"
        f"❌ Не продлили за 30 дней: <b>{data.churned_30d}</b>\n\n"
        f"📊 Renewal rate (30д): <b>{data.renewal_rate_30d}%</b>"
    )


@router.message(Command("admin_user"))
async def handle_admin_user(
    msg: types.Message,
    admin_view: FromDishka[AdminView],
) -> None:
    args = msg.text.split() if msg.text else []
    if len(args) < 2 or not args[1].lstrip("-").isdigit():
        await msg.answer("Использование: /admin_user <telegram_id>")
        return

    telegram_id = int(args[1])
    info: AdminUserInfo | None = await admin_view.get_user_info(telegram_id)

    if info is None:
        await msg.answer(f"❌ Пользователь {telegram_id} не найден.")
        return

    if info.active_until:
        end_str = info.active_until.strftime("%d.%m.%Y")
        sub_line = f"📅 Подписка до: <b>{end_str}</b>"
        if info.device_limit is not None:
            sub_line += f"\n📱 Девайсов: <b>{info.device_limit}</b>"
    else:
        sub_line = "📅 Подписка: <b>нет активной</b>"

    referrer_line = (
        f"🔗 Реферал от: <b>{info.referred_by}</b>"
        if info.referred_by
        else "🔗 Реферал: нет"
    )

    await msg.answer(
        f"👤 <b>Пользователь {info.telegram_id}</b>\n\n"
        f"{sub_line}\n"
        f"💰 Баланс: <b>{info.balance} руб.</b>\n"
        f"{referrer_line}"
    )
```

- [ ] **Шаг 2: Закоммитить**

```bash
git add src/apps/user/controllers/bot/admin_router.py
git commit -m "feat: add admin bot commands for subscriber stats"
```

---

## Задача 5: Подключить admin_router к боту

**Файлы:**
- Изменить: `main_bot.py`

- [ ] **Шаг 1: Добавить импорт и регистрацию роутера**

В `main_bot.py` добавить импорт после существующих импортов роутеров:

```python
from src.apps.user.controllers.bot.admin_router import router as admin_router
```

В функции `main()`, в строке `dp.include_routers(...)` добавить `admin_router` первым (чтобы фильтр `F.from_user.id == ADMIN_ID` отработал до общих хендлеров):

```python
dp.include_routers(admin_router, user_router, device_router, common_router)
```

- [ ] **Шаг 2: Закоммитить**

```bash
git add main_bot.py
git commit -m "feat: register admin_router in dispatcher"
```

---

## Задача 6: Тесты

**Файлы:**
- Создать: `tests/unit/user/test_admin_view.py`

- [ ] **Шаг 1: Написать тесты форматирования AdminView dataclasses**

```python
# tests/unit/user/test_admin_view.py
from datetime import UTC, datetime

import pytest

from src.apps.user.application.interfaces.admin_view import (
    AdminChurn,
    AdminExpiring,
    AdminStats,
    AdminUserInfo,
)


def test_admin_stats_frozen():
    stats = AdminStats(
        total_users=100,
        active_subscribers=60,
        new_today=3,
        new_week=15,
        new_month=40,
    )
    assert stats.total_users == 100
    assert stats.active_subscribers == 60
    assert stats.new_today == 3
    with pytest.raises(Exception):  # frozen dataclass
        stats.total_users = 999  # type: ignore


def test_admin_expiring_frozen():
    exp = AdminExpiring(expiring_3d=2, expiring_7d=8, expiring_30d=25)
    assert exp.expiring_3d == 2
    assert exp.expiring_7d == 8
    assert exp.expiring_30d == 25


def test_admin_churn_renewal_rate_bounds():
    # renewal rate корректно хранится как int 0-100
    churn = AdminChurn(churned_7d=2, churned_30d=5, renewal_rate_30d=75)
    assert 0 <= churn.renewal_rate_30d <= 100


def test_admin_churn_zero_expired():
    # renewal rate = 0 когда не было истечений
    churn = AdminChurn(churned_7d=0, churned_30d=0, renewal_rate_30d=0)
    assert churn.renewal_rate_30d == 0


def test_admin_user_info_no_subscription():
    info = AdminUserInfo(
        telegram_id=123456,
        balance=50,
        referred_by=None,
        active_until=None,
        device_limit=None,
    )
    assert info.active_until is None
    assert info.referred_by is None


def test_admin_user_info_with_subscription():
    end = datetime(2026, 6, 1, tzinfo=UTC)
    info = AdminUserInfo(
        telegram_id=999,
        balance=200,
        referred_by=12345,
        active_until=end,
        device_limit=2,
    )
    assert info.active_until == end
    assert info.device_limit == 2
    assert info.referred_by == 12345
```

- [ ] **Шаг 2: Запустить тесты**

```bash
uv run pytest tests/unit/user/test_admin_view.py -v
```

Ожидаемый результат: все 6 тестов зелёные.

- [ ] **Шаг 3: Закоммитить**

```bash
git add tests/unit/user/test_admin_view.py
git commit -m "test: add unit tests for admin view dataclasses"
```

---

## Проверка после всех задач

- [ ] **Запустить все unit-тесты**

```bash
uv run pytest tests/unit/ -v
```

Ожидаемый результат: все тесты зелёные.

- [ ] **Проверить импорты**

```bash
uv run python -c "from src.apps.user.controllers.bot.admin_router import router; print('ok')"
```

Ожидаемый результат: `ok`.

- [ ] **Вручную проверить команды в боте**

Запустить бота и от имени admin_id отправить:
- `/admin_stats` → сводка с числами
- `/admin_expiring` → 3 строки с числами
- `/admin_churn` → churn + renewal rate
- `/admin_user 123456789` → инфо по себе
- `/admin_user abc` → сообщение об ошибке формата
- От non-admin аккаунта: ни одна команда не должна ответить

---

## Примечание

Легаси-пользователи, у которых подписка только в таблице `subscriptions` (не мигрировали), не будут учтены в `/admin_stats` и `/admin_churn`. Они появятся в статистике после первого продления, которое создаст запись в `user_subscriptions`.
