# Infrastructure

Общая инфраструктура проекта: БД, DI, конфигурация, авторизация, логирование, планировщик.

## Database

### Структура

| Файл | Что делает |
|------|------------|
| `src/infrastructure/database/base.py` | `Base` (DeclarativeBase), `create_engine()`, `create_session_factory()` |
| `src/infrastructure/database/uow.py` | `SQLAlchemyUoW` — Unit of Work (commit, rollback, flush) |
| `src/infrastructure/database/provider.py` | `DatabaseProvider` — Dishka провайдер |

### Таблицы

| Таблица | ORM | Файл |
|---------|-----|------|
| `users` | `UserORM` | `src/apps/user/adapters/orm.py` |
| `devices` | `DeviceORM` | `src/apps/device/adapters/orm.py` |
| `subscriptions` | `SubscriptionORM` | `src/apps/device/adapters/orm.py` |
| `payments` | `PaymentORM` | `src/apps/device/adapters/orm.py` |
| `otp_codes` | `OtpCodeORM` | `src/apps/auth/adapters/orm.py` |
| `bot_auth_tokens` | `BotAuthTokenORM` | `src/apps/auth/adapters/orm.py` |

### Миграции

Alembic конфиг: `alembic.ini` + `alembic/env.py`. ORM импортируются в `env.py` для autogenerate.

```bash
uv run alembic upgrade head                      # применить
uv run alembic revision --autogenerate -m "msg"  # создать
```

---

## DI (Dishka)

### Корневой контейнер (`ioc.py`)

```python
create_container(config: AppConfig) -> AsyncContainer
```

Провайдеры:
1. `DatabaseProvider` — engine (APP), session + UoW (REQUEST)
2. `UserProvider` — gateway, view, interactor (REQUEST)
3. `DeviceProvider` — gateway, view, interactor (REQUEST)
4. `AuthProvider` — gateway, email_sender, interactor (REQUEST)

Контекст: `{AppConfig: config}`

### Scopes

| Scope | Что живёт |
|-------|-----------|
| `APP` | AsyncEngine (один на всё приложение) |
| `REQUEST` | AsyncSession, SQLAlchemyUoW, все Gateway/View/Interactor |

### Интеграции

- **Aiogram**: `setup_dishka(container, router=dp)` + `FromDishka[T]` в хендлерах
- **FastAPI**: `setup_dishka(container, app=app)` + `route_class=DishkaRoute` + `FromDishka[T]`

---

## Config (`src/infrastructure/config.py`)

`AppConfig(BaseSettings)` — загружает из `.env` с разделителем `__`.

| Секция | Класс | Ключевые поля | Префикс .env |
|--------|-------|---------------|-------------|
| database | `DatabaseSettings` | `url` | `DATABASE__` |
| bot | `BotSettings` | `token`, `bot_name`, `admin_id` | `BOT__` |
| payment | `PaymentSettings` | `payment_url`, `payment_qr`, `free_month` | `PAYMENT__` |
| remnawave | `RemnawaveSettings` | `url`, `token` | `REMNAWAVE__` |
| yookassa | `YooKassaSettings` | `shop_id`, `secret_key`, `return_url`, `enabled` (bool, default false) | `YOOKASSA__` |
| auth | `AuthSettings` | `jwt_secret`, `jwt_expire_minutes` (24h), `otp_expire_minutes` (5), `bot_token_expire_minutes` (10), `site_url` | `AUTH__` |
| smtp | `SmtpSettings` | `host`, `port`, `username`, `password`, `from_email` | `SMTP__` |
| logging | `LoggingSettings` | `log_level`, `log_json`, `log_to_file`, `log_dir` | `LOGGING__` |

Синглтон: `app_config = AppConfig()` — импортируется напрямую.

---

## Auth (`src/infrastructure/auth.py`)

JWT-авторизация для HTTP API.

| Функция | Назначение |
|---------|------------|
| `create_jwt(user_id: int) -> str` | Создать JWT с `sub=user_id`, `exp=now+24h` |
| `decode_jwt(token: str) -> int` | Декодировать JWT → user_id. Бросает HTTPException 401 |
| `get_current_user_id(request, cookie?) -> int` | FastAPI dependency: извлекает JWT из cookie или Bearer header |

`CurrentUser = Annotated[int, Depends(get_current_user_id)]` — используется в HTTP роутерах.

---

## SMTP (`src/infrastructure/smtp.py`)

`SmtpService` — реализует `EmailSender` Protocol. Отправляет OTP по email через aiosmtplib.

Настройки: `SmtpSettings` (Gmail SMTP по умолчанию).

---

## Logging (`src/infrastructure/logging/`)

| Файл | Что делает |
|------|------------|
| `setup.py` | Конфигурация structlog (JSON в файл, text в консоль) |

Вывод:
- `logs/app.jsonl` — все логи
- `logs/error.jsonl` — только ошибки

Middleware:
- **Aiogram**: добавляет `telegram_id` в контекст
- **FastAPI**: добавляет `request_id`, `method`, `path`, `duration_ms`

---

## Scheduler (`src/common/scheduler/tasks.py`)

**Framework**: APScheduler (`AsyncIOScheduler`)

**Задача**: `check_pending_subscriptions(bot, container)`
- **Расписание**: ежедневно в 09:00 (Asia/Yekaterinburg)
- **Логика**: `DeviceView.get_expiring_today()` → уведомление каждому юзеру → отчёт админу
- **Длинные отчёты**: если текст > 4000 символов — отправляется как файл `report.txt`

Настройка в `main_bot.py`:
```python
scheduler = AsyncIOScheduler(timezone="Asia/Yekaterinburg")
scheduler.add_job(check_pending_subscriptions, "cron", hour=9, ...)
```

---

## Точки входа

### `main_bot.py` — Telegram Bot

```
1. Загрузка config
2. Создание Bot + Dispatcher
3. Создание Dishka container
4. Подключение роутеров (user, device, common)
5. Подключение middleware (logging, state reset)
6. Регистрация команд (set_commands)
7. Запуск APScheduler
8. dp.start_polling()
```

### `main_web.py` — FastAPI API

```
1. Загрузка config
2. Lifespan: создаёт Bot (для уведомлений из webhook), кладёт в app.state.bot
3. Создание FastAPI app с lifespan
4. Создание Dishka container + setup_dishka
5. Подключение роутеров (auth, user, device, yookassa)
6. HTTP middleware (request logging)
7. Health check endpoint
```

---

## Файлы

| Файл | Назначение |
|------|------------|
| `ioc.py` | Корневой DI контейнер |
| `main_bot.py` | Точка входа бота |
| `main_web.py` | Точка входа API |
| `src/infrastructure/config.py` | Конфигурация (Pydantic Settings) |
| `src/infrastructure/auth.py` | JWT + CurrentUser dependency |
| `src/infrastructure/smtp.py` | Email отправка (aiosmtplib) |
| `src/infrastructure/database/base.py` | SQLAlchemy Base, engine, session factory |
| `src/infrastructure/database/uow.py` | Unit of Work |
| `src/infrastructure/database/provider.py` | Dishka DatabaseProvider |
| `src/infrastructure/logging/setup.py` | structlog конфигурация |
| `src/infrastructure/remnawave/` | Remnawave API клиент (`RemnawaveClient`, dataclasses) |
| `src/infrastructure/yookassa/client.py` | ЮKassa API клиент (`YooKassaClient`, `CreatedPayment`) |
| `src/common/scheduler/tasks.py` | Планировщик подписок |
| `src/common/bot/cbdata.py` | VpnCallback (callback data) |
| `src/common/bot/states.py` | FSM states |
| `src/common/bot/keyboards/` | Клавиатуры и кнопки |
| `src/common/bot/lexicon/` | Тексты сообщений |
| `src/common/bot/router.py` | Общий бот-роутер (help, errors) |
| `alembic/env.py` | Alembic environment |
| `docker-compose.yml` | PostgreSQL |
