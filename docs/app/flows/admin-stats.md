# Admin: статистика подписчиков

Telegram-команды только для администратора. Доступны через меню бота (scope `BotCommandScopeChat` с `admin_id`).

---

## Команды

| Команда | Что показывает |
|---------|---------------|
| `/admin_stats` | Всего пользователей, активных подписок, новых за день/неделю/месяц |
| `/admin_expiring` | Сколько подписок истекает за 3/7/30 дней |
| `/admin_churn` | Не продлили за 7/30 дней, renewal rate за 30 дней |
| `/admin_user` | Инфо по конкретному пользователю (подписка, баланс, реферал) |

---

## Безопасность

Роутер фильтруется на уровне `router.message.filter(F.from_user.id == ADMIN_ID)`. Все 4 команды недоступны другим пользователям — бот просто не отвечает на них.

---

## `/admin_user` — FSM-ввод

Поддерживает два варианта:
- `/admin_user 123456789` — ID передаётся аргументом, ответ сразу
- `/admin_user` (из меню) — бот спрашивает "Введите Telegram ID:", ждёт следующего сообщения

FSM-состояние: `AdminUserLookup.waiting_for_id`

Показывает: дату окончания подписки, лимит девайсов, баланс, telegram_id реферера.
Если пользователь есть только в легаси-таблице `subscriptions` (не мигрировал) — fallback через `devices → subscriptions`.

---

## Источники данных

Все данные — read-only через `AdminView` Protocol. Реализация: `SQLAlchemyAdminView`.

| Метод | Таблицы | Примечание |
|-------|---------|-----------|
| `get_stats()` | `users`, `user_subscriptions` | new_today/week/month по `users.created_at` (Date UTC) |
| `get_expiring()` | `user_subscriptions` | только новая модель подписок |
| `get_churn()` | `user_subscriptions` | churned = истекло без активной подписки; renewal_rate = round((expired - churned) / expired * 100) |
| `get_user_info()` | `users`, `user_subscriptions`, `subscriptions`, `devices` | fallback на легаси |

**Важно:** пользователи только в `subscriptions` (не мигрировали на Remnawave) не попадают в `/admin_stats` и `/admin_churn` до первого продления.

---

## Ключевые файлы

| Файл | Роль |
|------|------|
| `src/apps/user/application/interfaces/admin_view.py` | Protocol + dataclasses результатов |
| `src/apps/user/adapters/admin_view.py` | SQLAlchemy реализация |
| `src/apps/user/controllers/bot/admin_router.py` | Aiogram хендлеры |
| `src/apps/user/ioc.py` | DI регистрация `AdminView` |
| `src/common/bot/keyboards/commands.py` | Меню бота (admin scope) |
