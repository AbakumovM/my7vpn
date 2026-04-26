# Subscription Expiry Notifications — Design Spec

**Date:** 2026-04-26
**Status:** Approved

---

## Overview

Система уведомлений пользователей об истечении подписки. Уведомляет за 7, 3, 1 день до истечения и в день истечения. Работает через APScheduler, запускается ежедневно в 10:00 МСК. Idempotent: дубли исключены через таблицу `notification_log`.

Базируется на новой модели `UserSubscriptionORM`. Старый джоб `check_pending_subscriptions` и связанная функция удаляются.

---

## 1. Данные

### Новая таблица `notification_log`

```sql
CREATE TABLE notification_log (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    days_before  INTEGER NOT NULL,       -- 7, 3, 1, 0
    sub_end_date DATE NOT NULL,          -- дата окончания подписки
    sent_at      TIMESTAMPTZ NOT NULL,   -- когда фактически отправили
    UNIQUE (user_id, days_before, sub_end_date)
);
```

**Логика UNIQUE:** привязка к конкретной `sub_end_date`, а не к дате отправки.
- Рестарт в тот же день → дубль не пройдёт
- Продление подписки (новая `end_date`) → новые уведомления работают
- Один пользователь получает ровно одно уведомление каждого типа на каждую дату истечения

### ORM

Новый класс `NotificationLogORM` в `src/apps/device/adapters/orm.py`.

### Миграция

Новый файл через `alembic revision --autogenerate -m "add notification_log"`.

---

## 2. Архитектура

### Новые интерфейсы

**`src/apps/device/application/interfaces/notification_view.py`**

```python
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

**`src/apps/device/application/interfaces/notification_gateway.py`**

```python
class NotificationLogGateway(Protocol):
    async def is_sent(
        self, user_id: int, days_before: int, sub_end_date: date
    ) -> bool: ...

    async def mark_sent(
        self, user_id: int, days_before: int, sub_end_date: date
    ) -> None: ...
```

### Новые адаптеры

**`src/apps/device/adapters/notification_view.py`** — `SQLAlchemyNotificationView`
Один запрос к `UserSubscriptionORM` JOIN `UserORM` с фильтром:
```python
WHERE func.date(UserSubscriptionORM.end_date) IN (
    today + 7, today + 3, today + 1, today
) AND UserSubscriptionORM.is_active IS TRUE
```
Возвращает `list[ExpiringUserSubscriptionInfo]`, каждый с заполненным `days_before`.

**`src/apps/device/adapters/notification_gateway.py`** — `SQLAlchemyNotificationLogGateway`
- `is_sent`: SELECT по UNIQUE-ключу
- `mark_sent`: INSERT, при конфликте — игнорирует (ON CONFLICT DO NOTHING)

### Scheduler task

**`src/common/scheduler/tasks.py`** — новая функция `send_expiry_notifications(bot, container)`:

```
1. Получить NotificationView и NotificationLogGateway из контейнера
2. Вызвать get_subscriptions_to_notify([7, 3, 1, 0])
3. Для каждой записи:
   a. Проверить is_sent(user_id, days_before, end_date)
   b. Если уже отправлено — пропустить, увеличить счётчик skipped
   c. Отправить сообщение через bot.send_message (try/except)
   d. Если успешно — вызвать mark_sent, увеличить счётчик sent
   e. Если ошибка отправки — увеличить счётчик errors, залогировать
4. Отправить сводку администратору
```

### main_bot.py

- Timezone: `Europe/Moscow` (вместо `Asia/Yekaterinburg`)
- Время запуска: `10:00`
- Джоб: `send_expiry_notifications` (вместо `check_pending_subscriptions`)
- Старый импорт `check_pending_subscriptions` — удалить

### DI

В `src/apps/device/ioc.py` добавить провайдеры для:
- `SQLAlchemyNotificationView` → `NotificationView`
- `SQLAlchemyNotificationLogGateway` → `NotificationLogGateway`

Scope: `REQUEST` (оба используют `AsyncSession`).

---

## 3. Тексты уведомлений

Новый метод в `src/common/bot/lexicon/text_manager.py`:

```python
def subscription_expiry_notice(days_before: int, end_date: date) -> str: ...
```

| days_before | Текст |
|---|---|
| 7 | `📅 Ваша подписка истекает через 7 дней ({date}). Продлите заранее, чтобы не прерываться.` |
| 3 | `⏳ До окончания подписки осталось 3 дня ({date}). Не забудьте продлить.` |
| 1 | `⚠️ Завтра истекает ваша подписка ({date}). Продлите сегодня.` |
| 0 | `🔴 Сегодня истекает ваша подписка. Продлите, чтобы сохранить доступ к VPN.` |

К каждому сообщению прикрепляется inline-кнопка **"Продлить подписку"** — использует существующий `VpnCallback(action=VpnAction.RENEW).pack()` из `src/common/bot/keyboards/user_actions.py`.

---

## 4. Обработка ошибок

- **Ошибка отправки пользователю** — `try/except`, логируем через `structlog`, продолжаем. Бот заблокирован — тихо пропускаем.
- **Ошибка `mark_sent` после успешной отправки** — уведомление может уйти повторно при следующем запуске. Приемлемо как edge case.
- **Отчёт админу** после каждого прогона:
  ```
  🔔 Уведомления 26.04.2026 10:00
  📬 Отправлено: 12
  ⏭ Пропущено (уже отправлено): 3
  ❌ Ошибок: 1
  ```

---

## 5. Что удаляется

| Что | Где |
|---|---|
| Функция `check_pending_subscriptions` | `src/common/scheduler/tasks.py` |
| Функция `send_message_end_payments` | `src/common/scheduler/tasks.py` |
| Джоб `check_subscriptions` в APScheduler | `main_bot.py` |
| Метод `get_expiring_today` | `DeviceView` Protocol + `SQLAlchemyDeviceView` + `DeviceInteractor` (raise NotImplementedError) |

---

## 6. Файлы затронутые изменением

| Файл | Действие |
|---|---|
| `src/apps/device/adapters/orm.py` | добавить `NotificationLogORM` |
| `src/apps/device/application/interfaces/notification_view.py` | создать |
| `src/apps/device/application/interfaces/notification_gateway.py` | создать |
| `src/apps/device/adapters/notification_view.py` | создать |
| `src/apps/device/adapters/notification_gateway.py` | создать |
| `src/apps/device/application/interfaces/view.py` | удалить `get_expiring_today` |
| `src/apps/device/adapters/view.py` | удалить `get_expiring_today` |
| `src/apps/device/ioc.py` | добавить провайдеры |
| `src/common/scheduler/tasks.py` | заменить старые функции на `send_expiry_notifications` |
| `src/common/bot/lexicon/text_manager.py` | добавить `subscription_expiry_notice` |
| `main_bot.py` | сменить timezone, джоб, импорт |
| `alembic/versions/` | новая миграция для `notification_log` |
