# Миграция пользователей на Remnawave

---

## Контекст

Исторически подписки хранились в модели `Device → Subscription → Payment` (таблицы `devices`, `subscriptions`, `payments`). После перехода на Remnawave API появилась новая модель: `UserSubscription + UserPayment` (таблицы `user_subscriptions`, `user_payments`), а сам VPN-сервер управляется через Remnawave API.

Миграция — это перевод старых пользователей (у которых `remnawave_uuid = NULL`) на новую систему.

---

## Запуск миграции (admin only)

**Команда:** `/migrate_all`
**Файл:** `src/apps/device/controllers/bot/router.py` → `handle_admin_migrate_all()`

Что делает:
1. Получить всех пользователей без `remnawave_uuid`
2. Каждому отправить сообщение с кнопкой "🔑 Получить новый ключ"

---

## Флоу миграции (пользователь)

**Триггер:** `VpnCallback(action=VpnAction.MIGRATE)`
**Файл:** `src/apps/device/controllers/bot/router.py` → `handle_migrate_callback()`
**Интерактор:** `interactor.migrate_user_to_remnawave(MigrateUser(telegram_id))`

**Файл интерактора:** `src/apps/device/application/interactor.py` → `migrate_user_to_remnawave()`

### Шаги:

1. **Идемпотентность:** если `user.remnawave_uuid is not None` → уже мигрирован, вернуть текущий статус
2. Получить дату окончания старой подписки:
   ```python
   end_date = await self._device_gateway.get_active_subscription_end_date(telegram_id)
   ```
3. Создать аккаунт в Remnawave:
   ```python
   remnawave_user = await self._remnawave_gateway.create_user(
       telegram_id=telegram_id,
       expire_at=end_date,
       device_limit=1,
   )
   ```
4. Сохранить в User: `remnawave_uuid`, `subscription_url`
5. Создать `UserSubscription`:
   - `plan = (end_date - now).days` (остаток дней)
   - `start_date = now`, `end_date = end_date`
6. Создать `UserPayment`:
   - `amount = 0`, `payment_method = "migration"`

---

## Результат для пользователя

```
✅ Готово! Твоя подписка активна до DD.MM.YYYY.
Вот твой новый ключ подписки — скопируй и вставь в приложение Happ:
<code>{subscription_url}</code>
```

Плюс кнопка "📥 Скачать Happ".

---

## Особенности поля `plan` при миграции

При миграции `plan` = остаток дней (не месяцев). Это нормально — поле `plan: int` используется по-разному:
- Обычная подписка: месяцы (1, 3, 6, 12)
- Реферальный бесплатный период: дни (`app_config.payment.free_month`)
- Миграция: оставшиеся дни `(end_date - now).days`

---

## Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `src/apps/device/controllers/bot/router.py` | handle_admin_migrate_all, handle_migrate_callback |
| `src/apps/device/application/interactor.py` | migrate_user_to_remnawave |
| `src/apps/device/adapters/gateway.py` | get_active_subscription_end_date (берёт из старой модели) |
| `src/infrastructure/remnawave/client.py` | create_user |
| `src/common/bot/keyboards/keyboards.py` | get_keyboard_migrate |
