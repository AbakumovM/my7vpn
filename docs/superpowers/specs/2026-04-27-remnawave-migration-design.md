# Дизайн: Принудительная миграция пользователей на Remnawave

**Дата:** 2026-04-27
**Статус:** Утверждён

---

## Контекст

Все текущие пользователи имеют старые подписки (Device-модель, `remnawave_uuid IS NULL`). Новая система уже готова (Remnawave + UserSubscription), но пользователей на ней ещё нет. Нужно принудительно перевести всех активных пользователей на новую систему: отправить им уведомление с кнопкой, по нажатию создать Remnawave-аккаунт с их текущим сроком подписки.

---

## Цели

- Создать admin-команду `/migrate_all` для запуска рассылки
- При нажатии кнопки создать Remnawave-аккаунт с `device_limit=1` и `end_date` из старой подписки
- Детальный отчёт для админа после рассылки (с telegram_id проблемных пользователей)
- Идемпотентность: повторное нажатие кнопки не создаёт дублей
- Текст уведомления вынесен в `TextManager` для удобного редактирования

---

## Flow

```
Админ: /migrate_all
  ↓
Бот находит всех: remnawave_uuid IS NULL AND SubscriptionORM.end_date > now()
  ↓
Каждому отправляет уведомление с кнопкой "Получить новый ключ"
  (текст через TextManager.migration_notification(end_date))
  ↓
Админ получает отчёт: найдено / отправлено / ошибки с telegram_id
  ↓
Пользователь нажимает кнопку
  ↓
Бот создаёт Remnawave-аккаунт (expire_at=end_date, device_limit=1)
Создаёт UserSubscription + UserPayment(amount=0, method="migration")
  ↓
Отправляет пользователю subscription_url
```

---

## Секция 1: Новые компоненты

### `MigrationView` протокол

Файл: `src/apps/device/application/interfaces/migration_view.py`

```python
@dataclass(frozen=True)
class UserForMigrationInfo:
    user_id: int
    telegram_id: int
    end_date: datetime

class MigrationView(Protocol):
    async def get_users_for_migration(self) -> list[UserForMigrationInfo]: ...
```

### `SQLAlchemyMigrationView` реализация

Файл: `src/apps/device/adapters/migration_view.py`

Запрос: `UserORM JOIN DeviceORM JOIN SubscriptionORM` где:
- `UserORM.remnawave_uuid IS NULL`
- `SubscriptionORM.is_active = True`
- `SubscriptionORM.end_date > now()`

### Доменные объекты (в `src/apps/device/domain/commands.py`)

```python
@dataclass(frozen=True)
class MigrateUser:
    telegram_id: int

@dataclass(frozen=True)
class MigrateUserResult:
    subscription_url: str
    end_date: datetime
```

---

## Секция 2: Новый метод в DeviceGateway (старая Device-модель)

Файл: `src/apps/device/application/interfaces/gateway.py`

Новый метод в протоколе `DeviceGateway` (шлюз для старой таблицы `devices`):

```python
async def get_active_subscription_end_date(self, telegram_id: int) -> datetime: ...
```

Реализация в `src/apps/device/adapters/gateway.py`:

```sql
SELECT s.end_date
FROM subscriptions s
JOIN devices d ON s.device_id = d.id
JOIN users u ON d.user_id = u.id
WHERE u.telegram_id = :telegram_id
  AND s.is_active = True
  AND s.end_date > now()
ORDER BY s.end_date DESC
LIMIT 1
```

Если не найдено — поднимает `SubscriptionNotFound`.

---

## Секция 3: `migrate_user_to_remnawave` в DeviceInteractor

Файл: `src/apps/device/application/interactor.py`

```python
async def migrate_user_to_remnawave(cmd: MigrateUser) -> MigrateUserResult:
    user = await self._gateway.get_by_telegram_id(cmd.telegram_id)

    # Идемпотентность: уже мигрирован
    if user.remnawave_uuid is not None:
        active_sub = await self._subscription_gateway.get_active_by_telegram_id(cmd.telegram_id)
        return MigrateUserResult(
            subscription_url=user.subscription_url,
            end_date=active_sub.end_date,
        )

    # Берём end_date из старой подписки
    end_date = await self._device_gateway.get_active_subscription_end_date(cmd.telegram_id)

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
        user_id=user.id,
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
    await self._gateway.save(user)
    await self._uow.commit()

    return MigrateUserResult(
        subscription_url=user.subscription_url,
        end_date=end_date,
    )
```

---

## Секция 4: TextManager

Файл: `src/common/bot/lexicon/text_manager.py`

Новый статический метод:

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

Текст намеренно минимальный — редактируется вручную перед запуском рассылки.

---

## Секция 5: Bot-контроллеры

Файл: `src/apps/device/controllers/bot/router.py`

### `/migrate_all` (только для админа)

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
            log.warning("migration_notify_failed", telegram_id=user.telegram_id, error=str(e))

    await _send_migration_report(bot, ADMIN_ID, total=len(users), sent=sent, errors=errors)
```

### Кнопка пользователя `MIGRATE_TO_REMNAWAVE`

```python
@router.callback_query(VpnCallback.filter(F.action == VpnAction.MIGRATE_TO_REMNAWAVE))
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

### Отчёт для админа

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

    await send_long_message(bot, admin_id, report)
```

### Клавиатура

Файл: `src/common/bot/keyboards/keyboards.py`

```python
def get_keyboard_migrate() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🔑 Получить новый ключ",
            callback_data=VpnCallback(action=VpnAction.MIGRATE_TO_REMNAWAVE).pack(),
        )
    ]])
```

Файл: `src/common/bot/keyboards/user_actions.py` — добавить `MIGRATE_TO_REMNAWAVE` в `VpnAction`.

---

## Секция 6: DI и регистрация

Файл: `src/apps/device/ioc.py`

Зарегистрировать `MigrationView → SQLAlchemyMigrationView` в `DeviceProvider`.

---

## Файлы изменений

| Файл | Изменение |
|------|-----------|
| `src/apps/device/application/interfaces/migration_view.py` | Создать: протокол `MigrationView` + `UserForMigrationInfo` |
| `src/apps/device/adapters/migration_view.py` | Создать: `SQLAlchemyMigrationView` |
| `src/apps/device/domain/commands.py` | Добавить: `MigrateUser`, `MigrateUserResult` |
| `src/apps/device/application/interfaces/gateway.py` | Добавить: `get_active_subscription_end_date` |
| `src/apps/device/adapters/gateway.py` | Реализовать: `get_active_subscription_end_date` |
| `src/apps/device/application/interactor.py` | Добавить: `migrate_user_to_remnawave` |
| `src/common/bot/lexicon/text_manager.py` | Добавить: `migration_notification` |
| `src/common/bot/keyboards/keyboards.py` | Добавить: `get_keyboard_migrate` |
| `src/common/bot/keyboards/user_actions.py` | Добавить: `MIGRATE_TO_REMNAWAVE` в `VpnAction` |
| `src/apps/device/controllers/bot/router.py` | Добавить: `handle_admin_migrate_all`, `handle_migrate_callback`, `_send_migration_report` |
| `src/apps/device/ioc.py` | Зарегистрировать: `MigrationView` |

---

## Edge cases

| Ситуация | Поведение |
|----------|-----------|
| Пользователь нажал кнопку дважды | `remnawave_uuid is not None` → возвращаем текущие данные без создания дубля |
| Remnawave недоступен при нажатии | Исключение propagates → global error handler показывает стандартное сообщение |
| Пользователь заблокировал бота | `send_message` выбрасывает ошибку → попадает в список errors отчёта |
| Нет активной старой подписки | `SubscriptionNotFound` → error handler |

---

## Вне scope

- Миграция пользователей с истёкшей подпиской (отдельная задача)
- Редактирование текста уведомления (делается вручную в `TextManager` перед запуском)
- Повторная рассылка для тех кто не нажал кнопку
