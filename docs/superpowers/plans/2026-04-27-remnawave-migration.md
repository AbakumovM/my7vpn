# Remnawave Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Цель:** Реализовать admin-команду `/migrate_all` для принудительного переноса всех активных пользователей со старой Device-модели на Remnawave через уведомление с кнопкой.

**Архитектура:** `MigrationView` запрашивает пользователей со старой подпиской (`remnawave_uuid IS NULL`). Команда `/migrate_all` рассылает уведомления. По нажатию кнопки `DeviceInteractor.migrate_user_to_remnawave` создаёт Remnawave-аккаунт с `end_date` из старой подписки и `device_limit=1`, затем записывает `UserSubscription` + `UserPayment(amount=0, method="migration")`.

**Tech Stack:** Python 3.12, Aiogram 3, SQLAlchemy 2 async, Dishka, pytest-asyncio.

---

## Файловая структура

| Файл | Действие |
|------|----------|
| `src/apps/device/application/interfaces/migration_view.py` | Создать: протокол + `UserForMigrationInfo` |
| `src/apps/device/adapters/migration_view.py` | Создать: `SQLAlchemyMigrationView` |
| `src/apps/device/application/interfaces/gateway.py` | Изменить: добавить `get_active_subscription_end_date` |
| `src/apps/device/adapters/gateway.py` | Изменить: реализовать метод |
| `src/apps/device/domain/commands.py` | Изменить: добавить `MigrateUser` |
| `src/apps/device/application/interactor.py` | Изменить: добавить `migrate_user_to_remnawave` + `MigrateUserResult` |
| `src/common/bot/lexicon/text_manager.py` | Изменить: добавить `migration_notification` |
| `src/common/bot/keyboards/user_actions.py` | Изменить: добавить `MIGRATE` в `VpnAction` |
| `src/common/bot/keyboards/keyboards.py` | Изменить: добавить `get_keyboard_migrate` |
| `src/apps/device/controllers/bot/router.py` | Изменить: добавить 2 хендлера + `_send_migration_report` |
| `src/apps/device/ioc.py` | Изменить: зарегистрировать `MigrationView` |
| `tests/unit/device/test_migration_view.py` | Создать |
| `tests/unit/device/test_device_interactor.py` | Изменить: добавить тесты `migrate_user_to_remnawave` |

---

## Задача 1: MigrationView протокол и реализация

**Файлы:**
- Создать: `src/apps/device/application/interfaces/migration_view.py`
- Создать: `src/apps/device/adapters/migration_view.py`
- Создать: `tests/unit/device/test_migration_view.py`

- [ ] **Шаг 1: Написать тест**

```python
# tests/unit/device/test_migration_view.py
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.apps.device.adapters.migration_view import SQLAlchemyMigrationView


@pytest.fixture
def session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_returns_users_with_old_subscriptions(session):
    """Возвращает пользователей с remnawave_uuid IS NULL и активной подпиской."""
    now = datetime.now(UTC)
    future = now + timedelta(days=10)

    row1 = MagicMock()
    row1.id = 1
    row1.telegram_id = 111
    row1.end_date = future

    row2 = MagicMock()
    row2.id = 2
    row2.telegram_id = 222
    row2.end_date = future + timedelta(days=5)

    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([row1, row2]))
    session.execute = AsyncMock(return_value=mock_result)

    view = SQLAlchemyMigrationView(session)
    result = await view.get_users_for_migration()

    assert len(result) == 2
    assert result[0].telegram_id == 111
    assert result[0].end_date == future
    assert result[1].telegram_id == 222


@pytest.mark.asyncio
async def test_returns_empty_when_no_users(session):
    """Возвращает пустой список если нет подходящих пользователей."""
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    session.execute = AsyncMock(return_value=mock_result)

    view = SQLAlchemyMigrationView(session)
    result = await view.get_users_for_migration()

    assert result == []
```

- [ ] **Шаг 2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/unit/device/test_migration_view.py -v
```

Ожидаемый результат: `ModuleNotFoundError` или `ImportError`.

- [ ] **Шаг 3: Создать протокол**

```python
# src/apps/device/application/interfaces/migration_view.py
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class UserForMigrationInfo:
    user_id: int
    telegram_id: int
    end_date: datetime


class MigrationView(Protocol):
    async def get_users_for_migration(self) -> list[UserForMigrationInfo]: ...
```

- [ ] **Шаг 4: Создать реализацию**

```python
# src/apps/device/adapters/migration_view.py
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.device.adapters.orm import DeviceORM, SubscriptionORM
from src.apps.device.application.interfaces.migration_view import UserForMigrationInfo
from src.apps.user.adapters.orm import UserORM


class SQLAlchemyMigrationView:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_users_for_migration(self) -> list[UserForMigrationInfo]:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(
                UserORM.id,
                UserORM.telegram_id,
                SubscriptionORM.end_date,
            )
            .join(DeviceORM, DeviceORM.user_id == UserORM.id)
            .join(SubscriptionORM, SubscriptionORM.device_id == DeviceORM.id)
            .where(UserORM.remnawave_uuid.is_(None))
            .where(SubscriptionORM.is_active.is_(True))
            .where(SubscriptionORM.end_date > now)
            .distinct(UserORM.id)
            .order_by(UserORM.id, SubscriptionORM.end_date.desc())
        )
        return [
            UserForMigrationInfo(
                user_id=row.id,
                telegram_id=row.telegram_id,
                end_date=row.end_date,
            )
            for row in result
        ]
```

- [ ] **Шаг 5: Запустить тест — убедиться что проходит**

```bash
uv run pytest tests/unit/device/test_migration_view.py -v
```

Ожидаемый результат: `2 passed`.

- [ ] **Шаг 6: Закоммитить**

```bash
git add src/apps/device/application/interfaces/migration_view.py \
        src/apps/device/adapters/migration_view.py \
        tests/unit/device/test_migration_view.py
git commit -m "feat: add MigrationView protocol and SQLAlchemy implementation"
```

---

## Задача 2: `get_active_subscription_end_date` в DeviceGateway

**Файлы:**
- Изменить: `src/apps/device/application/interfaces/gateway.py`
- Изменить: `src/apps/device/adapters/gateway.py`
- Изменить: `tests/unit/device/test_device_interactor.py` (добавить фикстуру)

Этот метод нужен `DeviceInteractor.migrate_user_to_remnawave` для получения `end_date` из старой подписки.

- [ ] **Шаг 1: Добавить метод в протокол**

В файле `src/apps/device/application/interfaces/gateway.py` добавить метод после `delete`:

```python
from datetime import datetime  # добавить в импорты если нет

class DeviceGateway(Protocol):
    async def get_by_id(self, device_id: int) -> Device | None: ...
    async def get_by_name(self, device_name: str) -> Device | None: ...
    async def get_active_by_telegram_id(self, telegram_id: int) -> Device | None: ...
    async def get_next_seq(self) -> int: ...
    async def save(self, device: Device) -> None: ...
    async def delete(self, device: Device) -> None: ...
    async def get_active_subscription_end_date(self, telegram_id: int) -> datetime: ...
```

- [ ] **Шаг 2: Добавить реализацию в `SQLAlchemyDeviceGateway`**

В файле `src/apps/device/adapters/gateway.py` добавить метод в класс `SQLAlchemyDeviceGateway` после метода `delete`:

```python
async def get_active_subscription_end_date(self, telegram_id: int) -> datetime:
    from src.apps.device.domain.exceptions import SubscriptionNotFound  # noqa: PLC0415
    result = await self._session.execute(
        select(SubscriptionORM.end_date)
        .join(DeviceORM, SubscriptionORM.device_id == DeviceORM.id)
        .join(UserORM, DeviceORM.user_id == UserORM.id)
        .where(UserORM.telegram_id == telegram_id)
        .where(SubscriptionORM.is_active.is_(True))
        .where(SubscriptionORM.end_date > datetime.now(UTC))
        .order_by(SubscriptionORM.end_date.desc())
        .limit(1)
    )
    end_date = result.scalar_one_or_none()
    if end_date is None:
        raise SubscriptionNotFound
    return end_date
```

- [ ] **Шаг 3: Запустить все тесты — убедиться что ничего не сломалось**

```bash
uv run pytest tests/unit/ -v
```

Ожидаемый результат: все тесты проходят (кроме 2 заранее известных падений в `test_text_manager.py`).

- [ ] **Шаг 4: Закоммитить**

```bash
git add src/apps/device/application/interfaces/gateway.py \
        src/apps/device/adapters/gateway.py
git commit -m "feat: add get_active_subscription_end_date to DeviceGateway"
```

---

## Задача 3: `MigrateUser` команда и `MigrateUserResult`

**Файлы:**
- Изменить: `src/apps/device/domain/commands.py`
- Изменить: `src/apps/device/application/interactor.py`

- [ ] **Шаг 1: Добавить `MigrateUser` в commands.py**

В конец файла `src/apps/device/domain/commands.py` добавить:

```python
@dataclass(frozen=True)
class MigrateUser:
    telegram_id: int
```

- [ ] **Шаг 2: Добавить `MigrateUserResult` в interactor.py**

В файле `src/apps/device/application/interactor.py` добавить после `FreeSubscriptionInfo`:

```python
@dataclass(frozen=True)
class MigrateUserResult:
    subscription_url: str
    end_date: datetime
```

- [ ] **Шаг 3: Добавить импорт `MigrateUser` в interactor.py**

В блок импортов из `src.apps.device.domain.commands` добавить `MigrateUser`:

```python
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
```

- [ ] **Шаг 4: Написать тесты для `migrate_user_to_remnawave`**

В файл `tests/unit/device/test_device_interactor.py` добавить класс:

```python
class TestMigrateUserToRemnawave:
    @pytest.mark.asyncio
    async def test_creates_remnawave_account_and_subscription(
        self,
        interactor: DeviceInteractor,
        mock_user_gateway: AsyncMock,
        mock_gateway: AsyncMock,
        mock_remnawave_gateway: AsyncMock,
        mock_subscription_gateway: AsyncMock,
        mock_uow: AsyncMock,
    ):
        """Создаёт Remnawave-аккаунт, UserSubscription и UserPayment для пользователя."""
        from datetime import UTC, datetime, timedelta
        from src.apps.user.domain.models import User

        now = datetime.now(UTC)
        end_date = now + timedelta(days=15)

        user = User(telegram_id=123, balance=0, remnawave_uuid=None, subscription_url=None)
        user.id = 1

        mock_user_gateway.get_by_telegram_id.return_value = user
        mock_gateway.get_active_subscription_end_date.return_value = end_date
        mock_remnawave_gateway.create_user.return_value = MagicMock(
            uuid="new-uuid",
            subscription_url="https://sub.url/new",
        )
        mock_subscription_gateway.save.return_value = MagicMock()
        mock_subscription_gateway.save_payment.return_value = MagicMock()

        from src.apps.device.domain.commands import MigrateUser
        result = await interactor.migrate_user_to_remnawave(MigrateUser(telegram_id=123))

        assert result.subscription_url == "https://sub.url/new"
        assert result.end_date == end_date
        mock_remnawave_gateway.create_user.assert_called_once_with(
            telegram_id=123,
            expire_at=end_date,
            device_limit=1,
        )
        mock_subscription_gateway.save.assert_called_once()
        mock_subscription_gateway.save_payment.assert_called_once()
        mock_uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotent_when_already_migrated(
        self,
        interactor: DeviceInteractor,
        mock_user_gateway: AsyncMock,
        mock_subscription_gateway: AsyncMock,
    ):
        """Если remnawave_uuid уже есть — не создаёт дубль, возвращает текущие данные."""
        from datetime import UTC, datetime, timedelta
        from src.apps.user.domain.models import User
        from src.apps.device.domain.models import UserSubscription

        now = datetime.now(UTC)
        end_date = now + timedelta(days=10)

        user = User(
            telegram_id=123,
            balance=0,
            remnawave_uuid="existing-uuid",
            subscription_url="https://sub.url/existing",
        )
        user.id = 1

        active_sub = UserSubscription(
            user_telegram_id=123,
            plan=10,
            start_date=now,
            end_date=end_date,
            device_limit=1,
            is_active=True,
        )

        mock_user_gateway.get_by_telegram_id.return_value = user
        mock_subscription_gateway.get_active_by_telegram_id.return_value = active_sub

        from src.apps.device.domain.commands import MigrateUser
        result = await interactor.migrate_user_to_remnawave(MigrateUser(telegram_id=123))

        assert result.subscription_url == "https://sub.url/existing"
        assert result.end_date == end_date
        # Remnawave не вызывается
        from unittest.mock import AsyncMock
        mock_remnawave_gateway = AsyncMock()
        mock_remnawave_gateway.create_user.assert_not_called()
```

- [ ] **Шаг 5: Запустить тесты — убедиться что падают**

```bash
uv run pytest tests/unit/device/test_device_interactor.py::TestMigrateUserToRemnawave -v
```

Ожидаемый результат: `AttributeError` или `ImportError` — метод ещё не существует.

- [ ] **Шаг 6: Реализовать `migrate_user_to_remnawave` в interactor**

В класс `DeviceInteractor` в файл `src/apps/device/application/interactor.py` добавить метод:

```python
async def migrate_user_to_remnawave(self, cmd: MigrateUser) -> MigrateUserResult:
    user = await self._user_gateway.get_by_telegram_id(cmd.telegram_id)

    # Идемпотентность: уже мигрирован
    if user.remnawave_uuid is not None:
        active_sub = await self._subscription_gateway.get_active_by_telegram_id(
            cmd.telegram_id
        )
        return MigrateUserResult(
            subscription_url=user.subscription_url,
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
    payment = UserPayment(
        user_telegram_id=cmd.telegram_id,
        amount=0,
        duration=(end_date - now_dt).days,
        device_limit=1,
        payment_method="migration",
    )

    await self._subscription_gateway.save(subscription)
    await self._subscription_gateway.save_payment(payment)
    await self._user_gateway.save(user)
    await self._uow.commit()

    return MigrateUserResult(
        subscription_url=user.subscription_url,
        end_date=end_date,
    )
```

- [ ] **Шаг 7: Запустить тесты — убедиться что проходят**

```bash
uv run pytest tests/unit/device/test_device_interactor.py::TestMigrateUserToRemnawave -v
```

Ожидаемый результат: `2 passed`.

- [ ] **Шаг 8: Запустить все тесты**

```bash
uv run pytest tests/unit/ -v
```

Ожидаемый результат: все тесты проходят.

- [ ] **Шаг 9: Закоммитить**

```bash
git add src/apps/device/domain/commands.py \
        src/apps/device/application/interactor.py \
        tests/unit/device/test_device_interactor.py
git commit -m "feat: add MigrateUser command and migrate_user_to_remnawave interactor method"
```

---

## Задача 4: TextManager, VpnAction, клавиатура

**Файлы:**
- Изменить: `src/common/bot/lexicon/text_manager.py`
- Изменить: `src/common/bot/keyboards/user_actions.py`
- Изменить: `src/common/bot/keyboards/keyboards.py`

- [ ] **Шаг 1: Добавить `migration_notification` в TextManager**

В файл `src/common/bot/lexicon/text_manager.py` добавить метод в класс `TextManager`:

```python
@staticmethod
def migration_notification(end_date: datetime) -> str:
    return (
        f"🔄 Мы обновили сервис!\n\n"
        f"Нажми кнопку ниже чтобы получить новый ключ подписки.\n"
        f"Срок действия сохраняется: до {end_date.strftime('%d.%m.%Y')}.\n"
        f"Устройств: 1."
    )
```

Добавить в начало файла импорт если его нет:

```python
from datetime import date, datetime
```

- [ ] **Шаг 2: Добавить `MIGRATE` в `VpnAction`**

В файл `src/common/bot/keyboards/user_actions.py` добавить в `VpnAction`:

```python
class VpnAction(StrEnum):
    NEW = "new"
    RENEW = "renew"
    REFERRAL = "referral"
    MIGRATE = "migrate"
```

- [ ] **Шаг 3: Добавить `get_keyboard_migrate` в keyboards.py**

В файл `src/common/bot/keyboards/keyboards.py` добавить функцию:

```python
def get_keyboard_migrate() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🔑 Получить новый ключ",
                callback_data=VpnCallback(action=VpnAction.MIGRATE).pack(),
            )
        ]]
    )
```

- [ ] **Шаг 4: Запустить тесты**

```bash
uv run pytest tests/unit/ -v
```

Ожидаемый результат: все тесты проходят.

- [ ] **Шаг 5: Закоммитить**

```bash
git add src/common/bot/lexicon/text_manager.py \
        src/common/bot/keyboards/user_actions.py \
        src/common/bot/keyboards/keyboards.py
git commit -m "feat: add migration_notification text, MIGRATE action, migrate keyboard"
```

---

## Задача 5: Bot-контроллеры и DI

**Файлы:**
- Изменить: `src/apps/device/controllers/bot/router.py`
- Изменить: `src/apps/device/ioc.py`

- [ ] **Шаг 1: Добавить импорты в router.py**

В начало файла `src/apps/device/controllers/bot/router.py` добавить в существующие импорты:

```python
# В блок aiogram-импортов
from aiogram.filters import Command

# В импорты из src.apps.device
from src.apps.device.application.interfaces.migration_view import MigrationView
from src.apps.device.domain.commands import MigrateUser

# В импорты из src.common.bot.keyboards.keyboards
# (добавить к существующим)
from src.common.bot.keyboards.keyboards import (
    get_keyboard_admin_confirm,
    get_keyboard_approve_payment_or_cancel,
    get_keyboard_confirm_payment,
    get_keyboard_device_count,
    get_keyboard_migrate,
    get_keyboard_payment_link,
    get_keyboard_skip_email,
    get_keyboard_tariff,
    get_keyboard_vpn_received,
    return_start,
)

# В импорты TextManager
from src.common.bot.lexicon.text_manager import TextManager, bot_repl
```

- [ ] **Шаг 2: Добавить `_send_migration_report` в router.py**

В файл `src/apps/device/controllers/bot/router.py` добавить helper-функцию (после импортов, перед хендлерами):

```python
async def _send_migration_report(
    bot: Bot,
    admin_id: int,
    total: int,
    sent: int,
    errors: list[tuple[int, str]],
) -> None:
    error_lines = "\n".join(f"• {tid} — {err}" for tid, err in errors)
    report = (
        f"✅ Рассылка завершена.\n"
        f"📬 Найдено: {total} | ✉️ Отправлено: {sent} | ❌ Ошибок: {len(errors)}\n"
    )
    if errors:
        report += f"\nНе удалось отправить (telegram_id):\n{error_lines}"
    from src.common.scheduler.tasks import send_long_message  # noqa: PLC0415
    await send_long_message(bot, admin_id, report)
```

- [ ] **Шаг 3: Добавить хендлер `/migrate_all`**

В файл `src/apps/device/controllers/bot/router.py` добавить хендлер:

```python
@router.message(Command("migrate_all"))
async def handle_admin_migrate_all(
    msg: types.Message,
    bot: Bot,
    migration_view: FromDishka[MigrationView],
) -> None:
    if msg.from_user.id != ADMIN_ID:
        return

    users = await migration_view.get_users_for_migration()
    sent, errors = 0, []

    for user in users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=TextManager.migration_notification(user.end_date),
                reply_markup=get_keyboard_migrate(),
            )
            sent += 1
        except Exception as e:
            errors.append((user.telegram_id, str(e)))
            log.warning(
                "migration_notify_failed",
                telegram_id=user.telegram_id,
                error=str(e),
            )

    await _send_migration_report(bot, ADMIN_ID, total=len(users), sent=sent, errors=errors)
```

- [ ] **Шаг 4: Добавить хендлер кнопки миграции**

В файл `src/apps/device/controllers/bot/router.py` добавить хендлер:

```python
@router.callback_query(VpnCallback.filter(F.action == VpnAction.MIGRATE))
async def handle_migrate_callback(
    call: types.CallbackQuery,
    interactor: FromDishka[DeviceInteractor],
) -> None:
    result = await interactor.migrate_user_to_remnawave(
        MigrateUser(telegram_id=call.from_user.id)
    )
    await call.message.edit_text(
        f"✅ Готово! Твоя подписка активна до {result.end_date.strftime('%d.%m.%Y')}.\n\n"
        f"Вот твой новый ключ подписки:"
    )
    await call.message.answer(result.subscription_url)
    await call.answer()
```

- [ ] **Шаг 5: Зарегистрировать `MigrationView` в ioc.py**

В файл `src/apps/device/ioc.py` добавить в импорты:

```python
from src.apps.device.adapters.migration_view import SQLAlchemyMigrationView
from src.apps.device.application.interfaces.migration_view import MigrationView
```

В класс `DeviceProvider` добавить provider:

```python
@provide
def get_migration_view(self, session: AsyncSession) -> MigrationView:
    return SQLAlchemyMigrationView(session)
```

- [ ] **Шаг 6: Запустить ruff**

```bash
uv run ruff check --fix src/apps/device/controllers/bot/router.py \
    src/apps/device/ioc.py && uv run ruff format src/
```

Ожидаемый результат: `All checks passed` или только автоисправления.

- [ ] **Шаг 7: Запустить все тесты**

```bash
uv run pytest tests/unit/ -v
```

Ожидаемый результат: все тесты проходят.

- [ ] **Шаг 8: Закоммитить**

```bash
git add src/apps/device/controllers/bot/router.py \
        src/apps/device/ioc.py
git commit -m "feat: add /migrate_all command and migrate callback handler"
```
