# Subscription Expiry Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить ежедневные уведомления пользователям об истечении подписки за 7/3/1/0 дней с idempotent-логом отправки.

**Architecture:** APScheduler запускает `send_expiry_notifications` ежедневно в 10:00 МСК. `NotificationView` выбирает активные `UserSubscriptionORM` с нужными датами окончания. `NotificationLogGateway` хранит лог отправки в `notification_log` (UNIQUE constraint предотвращает дубли). Старый джоб `check_pending_subscriptions` и метод `get_expiring_today` удаляются.

**Tech Stack:** Python 3.12, SQLAlchemy 2 async, APScheduler, Aiogram 3, Dishka, PostgreSQL, pytest + pytest-asyncio

---

## File Map

| Файл | Действие |
|---|---|
| `src/apps/device/adapters/orm.py` | добавить `NotificationLogORM` |
| `src/apps/device/application/interfaces/notification_view.py` | создать |
| `src/apps/device/application/interfaces/notification_gateway.py` | создать |
| `src/apps/device/adapters/notification_view.py` | создать |
| `src/apps/device/adapters/notification_gateway.py` | создать |
| `src/apps/device/application/interfaces/view.py` | удалить `get_expiring_today` |
| `src/apps/device/adapters/view.py` | удалить `get_expiring_today` |
| `src/apps/device/application/interactor.py` | удалить `get_expiring_subscriptions` |
| `src/apps/device/domain/commands.py` | удалить `GetExpiringSubscriptions` |
| `src/apps/device/ioc.py` | добавить провайдеры |
| `src/common/bot/lexicon/text_manager.py` | добавить `subscription_expiry_notice` |
| `src/common/scheduler/tasks.py` | заменить старые функции на `send_expiry_notifications` |
| `main_bot.py` | сменить timezone, джоб, импорт |
| `alembic/versions/` | новая миграция |
| `tests/unit/device/test_notification_gateway.py` | создать |
| `tests/unit/device/test_notification_view.py` | создать |
| `tests/unit/device/test_send_expiry_notifications.py` | создать |
| `tests/unit/test_text_manager.py` | создать |

---

## Task 1: ORM — добавить NotificationLogORM

**Files:**
- Modify: `src/apps/device/adapters/orm.py`

- [ ] **Step 1: Добавить `NotificationLogORM` в конец файла**

Открыть `src/apps/device/adapters/orm.py`. После класса `UserPaymentORM` добавить:

```python
from sqlalchemy import Date, UniqueConstraint

class NotificationLogORM(Base):
    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    days_before = Column(Integer, nullable=False)
    sub_end_date = Column(Date, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "days_before", "sub_end_date", name="uq_notification_log"),
    )
```

Добавить `Date, UniqueConstraint` к существующему импорту из `sqlalchemy`:
```python
from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
```

- [ ] **Step 2: Создать Alembic-миграцию**

```bash
uv run alembic revision --autogenerate -m "add notification_log"
```

Открыть созданный файл в `alembic/versions/` и убедиться, что в `upgrade()` есть `op.create_table("notification_log", ...)` с колонками и `op.create_unique_constraint(...)`, а в `downgrade()` — `op.drop_table("notification_log")`.

- [ ] **Step 3: Применить миграцию**

```bash
uv run alembic upgrade head
```

Ожидаемый вывод: `Running upgrade ... -> ..., add notification_log`

- [ ] **Step 4: Коммит**

```bash
git add src/apps/device/adapters/orm.py alembic/versions/
git commit -m "feat: add NotificationLogORM and migration"
```

---

## Task 2: Interfaces — Protocol-файлы

**Files:**
- Create: `src/apps/device/application/interfaces/notification_view.py`
- Create: `src/apps/device/application/interfaces/notification_gateway.py`

- [ ] **Step 1: Создать `notification_view.py`**

```python
# src/apps/device/application/interfaces/notification_view.py
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class ExpiringUserSubscriptionInfo:
    user_id: int
    telegram_id: int
    end_date: date
    days_before: int  # 7, 3, 1, 0


class NotificationView(Protocol):
    async def get_subscriptions_to_notify(
        self, days_offsets: list[int]
    ) -> list[ExpiringUserSubscriptionInfo]: ...
```

- [ ] **Step 2: Создать `notification_gateway.py`**

```python
# src/apps/device/application/interfaces/notification_gateway.py
from datetime import date
from typing import Protocol


class NotificationLogGateway(Protocol):
    async def is_sent(
        self, user_id: int, days_before: int, sub_end_date: date
    ) -> bool: ...

    async def mark_sent(
        self, user_id: int, days_before: int, sub_end_date: date
    ) -> None: ...
```

- [ ] **Step 3: Коммит**

```bash
git add src/apps/device/application/interfaces/notification_view.py \
        src/apps/device/application/interfaces/notification_gateway.py
git commit -m "feat: add NotificationView and NotificationLogGateway protocols"
```

---

## Task 3: Adapter — SQLAlchemyNotificationLogGateway (TDD)

**Files:**
- Create: `tests/unit/device/test_notification_gateway.py`
- Create: `src/apps/device/adapters/notification_gateway.py`

- [ ] **Step 1: Написать тесты**

```python
# tests/unit/device/test_notification_gateway.py
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.notification_gateway import SQLAlchemyNotificationLogGateway


pytestmark = pytest.mark.asyncio


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def gateway(session: AsyncMock) -> SQLAlchemyNotificationLogGateway:
    return SQLAlchemyNotificationLogGateway(session)


async def test_is_sent_returns_true_when_record_exists(
    gateway: SQLAlchemyNotificationLogGateway, session: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 42  # id exists
    session.execute = AsyncMock(return_value=mock_result)

    result = await gateway.is_sent(user_id=1, days_before=7, sub_end_date=date(2026, 5, 1))

    assert result is True


async def test_is_sent_returns_false_when_no_record(
    gateway: SQLAlchemyNotificationLogGateway, session: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    result = await gateway.is_sent(user_id=1, days_before=7, sub_end_date=date(2026, 5, 1))

    assert result is False


async def test_mark_sent_executes_and_commits(
    gateway: SQLAlchemyNotificationLogGateway, session: AsyncMock
) -> None:
    await gateway.mark_sent(user_id=1, days_before=3, sub_end_date=date(2026, 5, 1))

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

```bash
uv run pytest tests/unit/device/test_notification_gateway.py -v
```

Ожидаемый вывод: `ImportError` или `ModuleNotFoundError` — файл адаптера ещё не создан.

- [ ] **Step 3: Реализовать `SQLAlchemyNotificationLogGateway`**

```python
# src/apps/device/adapters/notification_gateway.py
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import NotificationLogORM


class SQLAlchemyNotificationLogGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_sent(self, user_id: int, days_before: int, sub_end_date: date) -> bool:
        result = await self._session.execute(
            select(NotificationLogORM.id)
            .where(NotificationLogORM.user_id == user_id)
            .where(NotificationLogORM.days_before == days_before)
            .where(NotificationLogORM.sub_end_date == sub_end_date)
        )
        return result.scalar_one_or_none() is not None

    async def mark_sent(self, user_id: int, days_before: int, sub_end_date: date) -> None:
        stmt = pg_insert(NotificationLogORM).values(
            user_id=user_id,
            days_before=days_before,
            sub_end_date=sub_end_date,
            sent_at=datetime.now(UTC),
        ).on_conflict_do_nothing(
            index_elements=["user_id", "days_before", "sub_end_date"]
        )
        await self._session.execute(stmt)
        await self._session.commit()
```

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

```bash
uv run pytest tests/unit/device/test_notification_gateway.py -v
```

Ожидаемый вывод: `3 passed`

- [ ] **Step 5: Коммит**

```bash
git add tests/unit/device/test_notification_gateway.py \
        src/apps/device/adapters/notification_gateway.py
git commit -m "feat: add SQLAlchemyNotificationLogGateway with tests"
```

---

## Task 4: Adapter — SQLAlchemyNotificationView (TDD)

**Files:**
- Create: `tests/unit/device/test_notification_view.py`
- Create: `src/apps/device/adapters/notification_view.py`

- [ ] **Step 1: Написать тесты**

```python
# tests/unit/device/test_notification_view.py
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.notification_view import SQLAlchemyNotificationView
from src.apps.device.application.interfaces.notification_view import ExpiringUserSubscriptionInfo


pytestmark = pytest.mark.asyncio


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def view(session: AsyncMock) -> SQLAlchemyNotificationView:
    return SQLAlchemyNotificationView(session)


def _make_row(user_id: int, telegram_id: int, end_date: date) -> MagicMock:
    row = MagicMock()
    row.id = user_id
    row.telegram_id = telegram_id
    # SQLAlchemy возвращает datetime с timezone для DateTime(timezone=True)
    row.end_date = datetime(end_date.year, end_date.month, end_date.day, tzinfo=timezone.utc)
    return row


async def test_get_subscriptions_to_notify_returns_correct_days_before(
    view: SQLAlchemyNotificationView, session: AsyncMock
) -> None:
    today = date.today()
    end_in_7 = today + timedelta(days=7)
    end_in_1 = today + timedelta(days=1)

    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([
        _make_row(user_id=1, telegram_id=100, end_date=end_in_7),
        _make_row(user_id=2, telegram_id=200, end_date=end_in_1),
    ]))
    session.execute = AsyncMock(return_value=mock_result)

    result = await view.get_subscriptions_to_notify([7, 3, 1, 0])

    assert len(result) == 2
    item_7 = next(r for r in result if r.user_id == 1)
    item_1 = next(r for r in result if r.user_id == 2)
    assert item_7.days_before == 7
    assert item_7.end_date == end_in_7
    assert item_1.days_before == 1
    assert item_1.end_date == end_in_1


async def test_get_subscriptions_to_notify_returns_empty_when_no_subscriptions(
    view: SQLAlchemyNotificationView, session: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    session.execute = AsyncMock(return_value=mock_result)

    result = await view.get_subscriptions_to_notify([7, 3, 1, 0])

    assert result == []
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

```bash
uv run pytest tests/unit/device/test_notification_view.py -v
```

Ожидаемый вывод: `ImportError` — файл ещё не создан.

- [ ] **Step 3: Реализовать `SQLAlchemyNotificationView`**

```python
# src/apps/device/adapters/notification_view.py
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import UserSubscriptionORM
from src.apps.device.application.interfaces.notification_view import ExpiringUserSubscriptionInfo
from src.apps.user.adapters.orm import UserORM


class SQLAlchemyNotificationView:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_subscriptions_to_notify(
        self, days_offsets: list[int]
    ) -> list[ExpiringUserSubscriptionInfo]:
        today = date.today()
        target_dates = {offset: today + timedelta(days=offset) for offset in days_offsets}

        conditions = [
            func.date(UserSubscriptionORM.end_date) == target_date
            for target_date in target_dates.values()
        ]

        result = await self._session.execute(
            select(
                UserORM.id,
                UserORM.telegram_id,
                UserSubscriptionORM.end_date,
            )
            .join(UserSubscriptionORM, UserSubscriptionORM.user_id == UserORM.id)
            .where(or_(*conditions))
            .where(UserSubscriptionORM.is_active.is_(True))
        )

        date_to_days: dict[date, int] = {v: k for k, v in target_dates.items()}

        items: list[ExpiringUserSubscriptionInfo] = []
        for row in result:
            end_as_date = row.end_date.date() if hasattr(row.end_date, "date") else row.end_date
            days_before = date_to_days.get(end_as_date, 0)
            items.append(
                ExpiringUserSubscriptionInfo(
                    user_id=row.id,
                    telegram_id=row.telegram_id,
                    end_date=end_as_date,
                    days_before=days_before,
                )
            )
        return items
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/unit/device/test_notification_view.py -v
```

Ожидаемый вывод: `2 passed`

- [ ] **Step 5: Коммит**

```bash
git add tests/unit/device/test_notification_view.py \
        src/apps/device/adapters/notification_view.py
git commit -m "feat: add SQLAlchemyNotificationView with tests"
```

---

## Task 5: Text — subscription_expiry_notice (TDD)

**Files:**
- Create: `tests/unit/test_text_manager.py`
- Modify: `src/common/bot/lexicon/text_manager.py`

- [ ] **Step 1: Написать тесты**

```python
# tests/unit/test_text_manager.py
from datetime import date

import pytest

from src.common.bot.lexicon.text_manager import TextManager


def test_expiry_notice_7_days() -> None:
    text = TextManager.subscription_expiry_notice(days_before=7, end_date=date(2026, 5, 1))
    assert "7 дней" in text
    assert "01.05.2026" in text


def test_expiry_notice_3_days() -> None:
    text = TextManager.subscription_expiry_notice(days_before=3, end_date=date(2026, 5, 1))
    assert "3 дня" in text
    assert "01.05.2026" in text


def test_expiry_notice_1_day() -> None:
    text = TextManager.subscription_expiry_notice(days_before=1, end_date=date(2026, 5, 1))
    assert "Завтра" in text
    assert "01.05.2026" in text


def test_expiry_notice_0_days() -> None:
    text = TextManager.subscription_expiry_notice(days_before=0, end_date=date(2026, 5, 1))
    assert "Сегодня" in text
    # Дата в тексте не нужна — подписка истекает сегодня
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

```bash
uv run pytest tests/unit/test_text_manager.py -v
```

Ожидаемый вывод: `AttributeError: type object 'TextManager' has no attribute 'subscription_expiry_notice'`

- [ ] **Step 3: Добавить метод в `TextManager`**

Открыть `src/common/bot/lexicon/text_manager.py`. Найти конец класса `TextManager` и добавить метод:

```python
    @staticmethod
    def subscription_expiry_notice(days_before: int, end_date: date) -> str:
        formatted = end_date.strftime("%d.%m.%Y")
        if days_before == 7:
            return (
                f"📅 Ваша подписка истекает через 7 дней ({formatted}).\n"
                f"Продлите заранее, чтобы не прерываться."
            )
        if days_before == 3:
            return (
                f"⏳ До окончания подписки осталось 3 дня ({formatted}).\n"
                f"Не забудьте продлить."
            )
        if days_before == 1:
            return (
                f"⚠️ Завтра истекает ваша подписка ({formatted}).\n"
                f"Продлите сегодня."
            )
        return (
            "🔴 Сегодня истекает ваша подписка.\n"
            "Продлите, чтобы сохранить доступ к VPN."
        )
```

Добавить `date` в импорты в начале файла (если ещё нет):
```python
from datetime import date
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/unit/test_text_manager.py -v
```

Ожидаемый вывод: `4 passed`

- [ ] **Step 5: Коммит**

```bash
git add tests/unit/test_text_manager.py src/common/bot/lexicon/text_manager.py
git commit -m "feat: add subscription_expiry_notice to TextManager"
```

---

## Task 6: Scheduler task — send_expiry_notifications (TDD)

**Files:**
- Create: `tests/unit/device/test_send_expiry_notifications.py`
- Modify: `src/common/scheduler/tasks.py`

- [ ] **Step 1: Написать тесты**

```python
# tests/unit/device/test_send_expiry_notifications.py
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.apps.device.application.interfaces.notification_gateway import NotificationLogGateway
from src.apps.device.application.interfaces.notification_view import (
    ExpiringUserSubscriptionInfo,
    NotificationView,
)
from src.common.scheduler.tasks import send_expiry_notifications


pytestmark = pytest.mark.asyncio


def _make_sub(user_id: int, telegram_id: int, days_before: int) -> ExpiringUserSubscriptionInfo:
    return ExpiringUserSubscriptionInfo(
        user_id=user_id,
        telegram_id=telegram_id,
        end_date=date.today() + timedelta(days=days_before),
        days_before=days_before,
    )


@pytest.fixture
def mock_bot() -> AsyncMock:
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_view() -> AsyncMock:
    return AsyncMock(spec=NotificationView)


@pytest.fixture
def mock_gateway() -> AsyncMock:
    return AsyncMock(spec=NotificationLogGateway)


@pytest.fixture
def mock_container(mock_view: AsyncMock, mock_gateway: AsyncMock) -> MagicMock:
    request_container = AsyncMock()
    request_container.get = AsyncMock(side_effect=lambda cls: {
        NotificationView: mock_view,
        NotificationLogGateway: mock_gateway,
    }[cls])

    container = MagicMock()
    container.return_value.__aenter__ = AsyncMock(return_value=request_container)
    container.return_value.__aexit__ = AsyncMock(return_value=False)
    return container


async def test_sends_notification_when_not_sent(
    mock_bot: AsyncMock,
    mock_view: AsyncMock,
    mock_gateway: AsyncMock,
    mock_container: MagicMock,
) -> None:
    mock_view.get_subscriptions_to_notify = AsyncMock(
        return_value=[_make_sub(user_id=1, telegram_id=100, days_before=7)]
    )
    mock_gateway.is_sent = AsyncMock(return_value=False)
    mock_gateway.mark_sent = AsyncMock()

    await send_expiry_notifications(bot=mock_bot, container=mock_container)

    mock_bot.send_message.assert_awaited_once()
    call_kwargs = mock_bot.send_message.call_args
    assert call_kwargs.kwargs["chat_id"] == 100
    mock_gateway.mark_sent.assert_awaited_once_with(
        user_id=1,
        days_before=7,
        sub_end_date=_make_sub(1, 100, 7).end_date,
    )


async def test_skips_already_sent(
    mock_bot: AsyncMock,
    mock_view: AsyncMock,
    mock_gateway: AsyncMock,
    mock_container: MagicMock,
) -> None:
    mock_view.get_subscriptions_to_notify = AsyncMock(
        return_value=[_make_sub(user_id=1, telegram_id=100, days_before=3)]
    )
    mock_gateway.is_sent = AsyncMock(return_value=True)

    await send_expiry_notifications(bot=mock_bot, container=mock_container)

    mock_bot.send_message.assert_not_awaited()
    mock_gateway.mark_sent.assert_not_awaited()


async def test_continues_on_send_error(
    mock_bot: AsyncMock,
    mock_view: AsyncMock,
    mock_gateway: AsyncMock,
    mock_container: MagicMock,
) -> None:
    mock_view.get_subscriptions_to_notify = AsyncMock(
        return_value=[
            _make_sub(user_id=1, telegram_id=100, days_before=1),
            _make_sub(user_id=2, telegram_id=200, days_before=1),
        ]
    )
    mock_gateway.is_sent = AsyncMock(return_value=False)
    mock_gateway.mark_sent = AsyncMock()
    mock_bot.send_message = AsyncMock(side_effect=[Exception("blocked"), None])

    await send_expiry_notifications(bot=mock_bot, container=mock_container)

    assert mock_bot.send_message.await_count == 2
    # Только второй успешно отправлен — mark_sent вызван один раз
    mock_gateway.mark_sent.assert_awaited_once()
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

```bash
uv run pytest tests/unit/device/test_send_expiry_notifications.py -v
```

Ожидаемый вывод: `ImportError` — `send_expiry_notifications` ещё не существует.

- [ ] **Step 3: Заменить содержимое `src/common/scheduler/tasks.py`**

```python
# src/common/scheduler/tasks.py
from datetime import datetime
from io import StringIO

import structlog
from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from dishka import AsyncContainer

from src.apps.device.application.interfaces.notification_gateway import NotificationLogGateway
from src.apps.device.application.interfaces.notification_view import NotificationView
from src.common.bot.keyboards.user_actions import VpnAction, VpnCallback
from src.common.bot.lexicon.text_manager import TextManager
from src.infrastructure.config import app_config

ADMIN_ID = app_config.bot.admin_id
log = structlog.get_logger(__name__)

NOTIFICATION_DAYS = [7, 3, 1, 0]


def _renew_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🔄 Продлить подписку",
            callback_data=VpnCallback(action=VpnAction.RENEW).pack(),
        )
    ]])


async def send_expiry_notifications(bot: Bot, container: AsyncContainer) -> None:
    log.info("notification_job_started")
    sent = 0
    skipped = 0
    errors = 0

    async with container() as request_container:
        view = await request_container.get(NotificationView)
        gateway = await request_container.get(NotificationLogGateway)
        subscriptions = await view.get_subscriptions_to_notify(NOTIFICATION_DAYS)

    for sub in subscriptions:
        if await gateway.is_sent(sub.user_id, sub.days_before, sub.end_date):
            skipped += 1
            continue
        try:
            text = TextManager.subscription_expiry_notice(sub.days_before, sub.end_date)
            await bot.send_message(
                chat_id=sub.telegram_id,
                text=text,
                reply_markup=_renew_keyboard(),
            )
            await gateway.mark_sent(sub.user_id, sub.days_before, sub.end_date)
            log.info(
                "notification_sent",
                telegram_id=sub.telegram_id,
                days_before=sub.days_before,
                end_date=str(sub.end_date),
            )
            sent += 1
        except Exception:
            log.exception(
                "notification_send_failed",
                telegram_id=sub.telegram_id,
                days_before=sub.days_before,
            )
            errors += 1

    log.info("notification_job_done", sent=sent, skipped=skipped, errors=errors)

    report = (
        f"🔔 Уведомления {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"📬 Отправлено: {sent}\n"
        f"⏭ Пропущено (уже отправлено): {skipped}\n"
        f"❌ Ошибок: {errors}"
    )
    try:
        await send_long_message(bot, ADMIN_ID, report)
    except Exception:
        log.exception("notification_admin_report_failed")


async def send_long_message(bot: Bot, chat_id: int, text: str, max_len: int = 4000) -> None:
    if len(text) <= max_len:
        await bot.send_message(chat_id=chat_id, text=text)
    else:
        buffer = StringIO()
        buffer.write(text)
        buffer.seek(0)
        input_file = BufferedInputFile(buffer.getvalue().encode("utf-8"), filename="report.txt")
        await bot.send_document(chat_id=chat_id, document=input_file)
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/unit/device/test_send_expiry_notifications.py -v
```

Ожидаемый вывод: `3 passed`

- [ ] **Step 5: Коммит**

```bash
git add tests/unit/device/test_send_expiry_notifications.py \
        src/common/scheduler/tasks.py
git commit -m "feat: add send_expiry_notifications scheduler task"
```

---

## Task 7: DI — зарегистрировать провайдеры

**Files:**
- Modify: `src/apps/device/ioc.py`

- [ ] **Step 1: Добавить провайдеры в `DeviceProvider`**

Открыть `src/apps/device/ioc.py`. Добавить импорты:

```python
from src.apps.device.adapters.notification_gateway import SQLAlchemyNotificationLogGateway
from src.apps.device.adapters.notification_view import SQLAlchemyNotificationView
from src.apps.device.application.interfaces.notification_gateway import NotificationLogGateway
from src.apps.device.application.interfaces.notification_view import NotificationView
```

Добавить методы в класс `DeviceProvider` (после `get_view`):

```python
    @provide
    def get_notification_view(self, session: AsyncSession) -> NotificationView:
        return SQLAlchemyNotificationView(session)

    @provide
    def get_notification_gateway(self, session: AsyncSession) -> NotificationLogGateway:
        return SQLAlchemyNotificationLogGateway(session)
```

- [ ] **Step 2: Проверить импорты проходят**

```bash
uv run python -c "from src.apps.device.ioc import DeviceProvider; print('OK')"
```

Ожидаемый вывод: `OK`

- [ ] **Step 3: Коммит**

```bash
git add src/apps/device/ioc.py
git commit -m "feat: register NotificationView and NotificationLogGateway in DI"
```

---

## Task 8: main_bot.py — обновить планировщик

**Files:**
- Modify: `main_bot.py`

- [ ] **Step 1: Заменить импорт и настройки джоба**

Открыть `main_bot.py`. Найти строку:
```python
from src.common.scheduler.tasks import check_pending_subscriptions
```
Заменить на:
```python
from src.common.scheduler.tasks import send_expiry_notifications
```

- [ ] **Step 2: Обновить timezone и джоб в `main()`**

Найти блок:
```python
    scheduler = AsyncIOScheduler(timezone=zoneinfo.ZoneInfo("Asia/Yekaterinburg"))
    scheduler.add_job(
        check_pending_subscriptions,
        trigger=CronTrigger(hour=9, minute=0),
        id="check_subscriptions",
        kwargs={"bot": bot, "container": container},
    )
```

Заменить на:
```python
    scheduler = AsyncIOScheduler(timezone=zoneinfo.ZoneInfo("Europe/Moscow"))
    scheduler.add_job(
        send_expiry_notifications,
        trigger=CronTrigger(hour=10, minute=0),
        id="send_expiry_notifications",
        kwargs={"bot": bot, "container": container},
    )
```

- [ ] **Step 3: Обновить id при чтении следующего запуска**

Найти:
```python
    job = scheduler.get_job("check_subscriptions")
```
Заменить на:
```python
    job = scheduler.get_job("send_expiry_notifications")
```

- [ ] **Step 4: Проверить запуск без ошибок**

```bash
uv run python -c "
import asyncio, sys
sys.exit(0)
"
# Проверяем только импорты main_bot.py
uv run python -c "import main_bot; print('imports OK')"
```

Ожидаемый вывод: `imports OK`

- [ ] **Step 5: Коммит**

```bash
git add main_bot.py
git commit -m "feat: switch scheduler to send_expiry_notifications, Europe/Moscow 10:00"
```

---

## Task 9: Cleanup — удалить старый код

**Files:**
- Modify: `src/apps/device/application/interfaces/view.py`
- Modify: `src/apps/device/adapters/view.py`
- Modify: `src/apps/device/application/interactor.py`
- Modify: `src/apps/device/domain/commands.py`

- [ ] **Step 1: Удалить `get_expiring_today` из `DeviceView` Protocol**

Открыть `src/apps/device/application/interfaces/view.py`.

Удалить датакласс `ExpiringSubscriptionInfo` (строки с `@dataclass(frozen=True)` до конца класса):
```python
@dataclass(frozen=True)
class ExpiringSubscriptionInfo:
    telegram_id: int
    device_name: str
    plan: int
    start_date: datetime
    end_date: datetime
```

Удалить метод из протокола:
```python
    async def get_expiring_today(self) -> list[ExpiringSubscriptionInfo]: ...
```

- [ ] **Step 2: Удалить реализацию из `SQLAlchemyDeviceView`**

Открыть `src/apps/device/adapters/view.py`.

Удалить импорт `date` из верхних строк (если он больше не используется в файле).

Удалить метод `get_expiring_today` полностью (строки 131–154).

- [ ] **Step 3: Удалить `get_expiring_subscriptions` из `DeviceInteractor`**

Открыть `src/apps/device/application/interactor.py`.

Удалить импорт `ExpiringSubscriptionInfo` из `view`:
```python
from src.apps.device.application.interfaces.view import ExpiringSubscriptionInfo
```

Удалить импорт команды `GetExpiringSubscriptions`:
```python
    GetExpiringSubscriptions,
```

Удалить метод:
```python
    async def get_expiring_subscriptions(
        self, cmd: GetExpiringSubscriptions
    ) -> list[ExpiringSubscriptionInfo]:
        raise NotImplementedError("Use DeviceView.get_expiring_today() directly")
```

- [ ] **Step 4: Удалить `GetExpiringSubscriptions` из `commands.py`**

Открыть `src/apps/device/domain/commands.py`.

Удалить датакласс:
```python
@dataclass(frozen=True)
class GetExpiringSubscriptions:
    pass
```

- [ ] **Step 5: Запустить все тесты**

```bash
uv run pytest tests/unit/ -v
```

Ожидаемый вывод: все тесты проходят, нет ошибок импорта.

- [ ] **Step 6: Коммит**

```bash
git add src/apps/device/application/interfaces/view.py \
        src/apps/device/adapters/view.py \
        src/apps/device/application/interactor.py \
        src/apps/device/domain/commands.py
git commit -m "refactor: remove get_expiring_today and GetExpiringSubscriptions"
```

---

## Task 10: Финальная проверка

- [ ] **Step 1: Запустить полный набор тестов**

```bash
uv run pytest tests/unit/ -v
```

Ожидаемый вывод: все тесты зелёные.

- [ ] **Step 2: Проверить линтер**

```bash
uv run ruff check src/ tests/
```

Ожидаемый вывод: нет ошибок (или только предупреждения, не связанные с новым кодом).

- [ ] **Step 3: Убедиться, что миграция применена**

```bash
uv run alembic current
```

Ожидаемый вывод: текущая версия совпадает с последней миграцией.
