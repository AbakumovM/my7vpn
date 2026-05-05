# API Audit & Frontend Readiness — Design Spec

**Date:** 2026-05-01
**Status:** Approved
**Branch:** web

---

## Context

Перед созданием фронтенда (личный кабинет) нужно убедиться что API покрывает весь функционал бота и работает консистентно. В ходе аудита выявлены критические гэпы: нет платёжного флоу через API, нет истории платежей, нет тарифной матрицы, а все операции завязаны на `telegram_id` — что делает web-only пользователей (вошедших через OTP email) гражданами второго сорта.

---

## Цель

1. Переключить primary identifier с `telegram_id` на `user_id` (int PK таблицы `users`) — единый ключ для всех случаев
2. Добавить недостающие эндпоинты для полноценного фронта
3. Зафиксировать финальную карту API

---

## Секция 1: user_id как главный идентификатор

### Что меняется

**Таблица `users` (без изменений структуры):**
```
users
├── id (int, PK)           ← user_id — новый главный ключ
├── telegram_id (bigint)   ← null для web-only; заполняется при взаимодействии с ботом
├── email (str, null)
├── balance (int)
├── remnawave_uuid (str)   ← UUID в VPN-панели Remnawave
└── web_key (str)          ← UUID для кабинета
```

**DB миграция — добавить user_id FK в зависимые таблицы:**
```sql
-- user_subscriptions
ALTER TABLE user_subscriptions ADD COLUMN user_id INTEGER REFERENCES users(id);
UPDATE user_subscriptions SET user_id = u.id
  FROM users u WHERE u.telegram_id = user_subscriptions.user_telegram_id;

-- user_payments
ALTER TABLE user_payments ADD COLUMN user_id INTEGER REFERENCES users(id);
UPDATE user_payments SET user_id = u.id
  FROM users u WHERE u.telegram_id = user_payments.user_telegram_id;

-- pending_payments
ALTER TABLE pending_payments ADD COLUMN user_id INTEGER REFERENCES users(id);
UPDATE pending_payments SET user_id = u.id
  FROM users u WHERE u.telegram_id = pending_payments.user_telegram_id;
```

Старый `user_telegram_id` остаётся — backward compatibility полная.

### Изменения по слоям

**Domain/Commands (`commands.py` × 2 домена):**
- `telegram_id: int` → `user_id: int` во всех командах

**Interfaces (gateway.py + view.py × 2 домена):**
- Добавить query-методы по `user_id`:
  `get_by_user_id(user_id)`, `get_subscription_info_by_user_id(user_id)`, etc.

**Interactors (`interactor.py` × 2 домена):**
- Принимают `user_id`, используют gateway-методы по `user_id`
- Для уведомлений через бот: дополнительно читают `telegram_id` из `users` — делаем lookup внутри interactor'а

**Adapters (gateway.py + view.py × 2 домена):**
- Добавить SQLAlchemy queries по `users.id`

**HTTP Controllers:**
- Уже получают `user_id` из JWT (`CurrentUser`) — изменений минимум, просто передают `user_id` в интеракторы

**Bot Controllers:**
- В начале каждого хендлера: `user_id = await user_view.get_user_id(telegram_id)`
- Далее все вызовы через `user_id`
- Admin-команды оставляют `telegram_id` как input (для admin lookup), но внутри переводят в `user_id`

### Сценарии идентификации

```
Telegram-пользователь:
  /start → get_or_create_user(telegram_id) → users(id=42, telegram_id=111)
  Web login via /web → JWT с user_id=42 ✅

Web-only пользователь (OTP email):
  OTP → users(id=55, telegram_id=null, email=user@example.com)
  JWT с user_id=55
  Может: смотреть профиль, историю, реферальный код
  Для подписки: нужен Telegram (bot-token login или будущий Login Widget)

Привязка аккаунтов (будущий Telegram Login Widget):
  Отдельная задача — merge web-аккаунта с Telegram-аккаунтом
```

---

## Секция 2: Новые эндпоинты

### GET /api/v1/tariffs

Без авторизации. Отдаёт тарифную матрицу для отображения на сайте.

```json
{
  "1": {"1": 150, "3": 400, "6": 700, "12": 1200},
  "2": {"1": 250, "3": 650, "6": 1100, "12": 1900},
  "3": {"1": 350, "3": 900, "6": 1500, "12": 2600}
}
```

Ключи: device_limit → plan_months → price_rub.

### POST /api/v1/payments/initiate

Требует JWT. Запускает платёжный флоу (аналог шагов 3–5 в боте).

```json
// Request
{
  "action": "new" | "renew",
  "plan": 1 | 3 | 6 | 12,
  "device_limit": 1 | 2 | 3
}

// Response
{
  "pending_id": 123,
  "amount": 400,
  "balance_used": 100,
  "final_amount": 300,
  "payment_url": "https://yookassa.ru/..." | null
}
```

Логика:
1. Вычислить `amount` из TARIFF_MATRIX
2. `balance_used = min(user.balance, amount)`, `final_amount = amount - balance_used`
3. `create_pending_payment(user_id, action, plan, device_limit, amount=final_amount, balance_to_deduct=balance_used)`
4. Если `final_amount == 0` → `payment_url = null` (сразу подтвердить через `/initiate/confirm`)
5. Иначе → `yookassa_client.create_payment(final_amount, pending_id)` → вернуть `payment_url`

Требует `telegram_id` для создания/обновления Remnawave-аккаунта. Если `telegram_id == null` → `403` с сообщением "Link Telegram to subscribe".

### POST /api/v1/payments/{pending_id}/confirm

Требует JWT. Подтверждает оплату бонусным балансом (когда `payment_url == null`).

```json
// Response (success)
{
  "subscription_url": "https://...",
  "end_date": "2026-06-01T00:00:00"
}
```

Вызывает `confirm_payment(pending_id, user_id)`.

### GET /api/v1/payments/{pending_id}/status

Требует JWT. Фронт опрашивает каждые 2–3 сек пока ждёт webhook от YooKassa.

```json
{
  "status": "pending" | "confirmed" | "rejected",
  "subscription_url": "https://..." | null,
  "end_date": "2026-06-01T00:00:00" | null
}
```

### GET /api/v1/payments/history

Требует JWT. История платежей пользователя.

```json
[
  {
    "id": 1,
    "amount": 400,
    "date": "2026-04-01T12:00:00",
    "plan": 3,
    "device_limit": 1,
    "payment_method": "карта",
    "status": "success"
  }
]
```

Читает из `user_payments WHERE user_id = current_user`, DESC по дате.

### Изменение: GET /api/v1/users/referral

Убрать ограничение "только для Telegram-пользователей". Для web-only генерировать `referral_code` от `user_id` (если нет `telegram_id`).

Логика генерации: `md5(str(user_id))[:8]` — аналогично текущей для telegram_id.

---

## Секция 3: Что остаётся без изменений

| Эндпоинт | Статус |
|----------|--------|
| `POST /api/v1/devices/` | Оставить как есть (internal/admin прямое создание) |
| `POST /api/v1/devices/{name}/renew` | Оставить как есть |
| `GET /api/v1/devices/` | Обновить query на `user_id` |
| `GET /api/v1/devices/{id}` | Обновить query на `user_id` |
| `DELETE /api/v1/devices/{id}` | Обновить query на `user_id` |
| `POST /api/v1/payments/yookassa/webhook` | Не трогаем |
| `GET /api/v1/cabinet/{web_key}` | Не трогаем |
| `DELETE /api/v1/cabinet/{web_key}/hwid/...` | Не трогаем |
| Auth endpoints | Не трогаем |

---

## Секция 4: Финальная карта API после изменений

| Метод | Путь | Auth | Назначение |
|-------|------|------|------------|
| GET | `/api/v1/tariffs` | None | Тарифная матрица |
| GET | `/api/v1/users/me` | JWT | Профиль: баланс, email, user_id |
| GET | `/api/v1/users/referral` | JWT | Реферальный код + статистика |
| GET | `/api/v1/devices/` | JWT | Список устройств/подписок |
| GET | `/api/v1/devices/{id}` | JWT | Детали подписки |
| POST | `/api/v1/payments/initiate` | JWT | Инициировать оплату (new/renew) |
| POST | `/api/v1/payments/{id}/confirm` | JWT | Подтвердить (бонусная оплата) |
| GET | `/api/v1/payments/{id}/status` | JWT | Статус pending payment |
| GET | `/api/v1/payments/history` | JWT | История платежей |
| POST | `/api/v1/payments/yookassa/webhook` | None | YooKassa webhook |
| GET | `/api/v1/cabinet/{web_key}` | WebKey | Кабинет (подписка + HWID) |
| DELETE | `/api/v1/cabinet/{web_key}/hwid/{hwid}` | WebKey | Удалить HWID устройство |
| DELETE | `/api/v1/cabinet/{web_key}/hwid` | WebKey | Удалить все HWID |
| POST | `/api/v1/auth/otp/request` | None | Запросить OTP код |
| POST | `/api/v1/auth/otp/verify` | None | Верифицировать OTP → JWT |
| GET | `/api/v1/auth/bot-token/{token}` | None | Bot-token → JWT |
| POST | `/api/v1/auth/logout` | JWT | Выйти |
| GET | `/api/v1/auth/me` | JWT | Проверить JWT |

---

## Секция 5: Вне скопа (отдельные задачи)

- **Telegram Login Widget** — привязка web-аккаунта к Telegram в браузере
- **Мёрдж аккаунтов** — объединение web-only и Telegram аккаунтов
- **Redis FSM Storage** — заменить MemoryStorage в боте
- **Webhook signature verification** — проверка подписи YooKassa
- **Rate limiting** — ограничение запросов

---

## Верификация

После имплементации проверить:

1. **Telegram-пользователь:** `/start` → `/web` → login → `GET /api/v1/users/me` → `POST /api/v1/payments/initiate` → YooKassa flow → `GET /api/v1/payments/{id}/status` = confirmed
2. **Web-only (OTP):** register → `GET /api/v1/users/me` → `GET /api/v1/users/referral` → `POST /api/v1/payments/initiate` = 403
3. **История:** после оплаты `GET /api/v1/payments/history` возвращает запись
4. **Тарифы:** `GET /api/v1/tariffs` без авторизации возвращает матрицу
5. **Бот:** все существующие flows (покупка, продление, реферал) продолжают работать
6. **DB:** после backfill-миграции `user_id` заполнен во всех `user_subscriptions` и `user_payments`
