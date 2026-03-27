# VPN Bot

Telegram-бот для управления VPN-подписками с веб-интерфейсом.

## Стек

- **Python 3.12+** — язык
- **Aiogram 3** — Telegram Bot API
- **FastAPI** — REST API для веб-интерфейса
- **SQLAlchemy 2 (async)** + **Alembic** — ORM и миграции
- **PostgreSQL** + **asyncpg** — база данных
- **Dishka** — Dependency Injection (поддерживает Aiogram и FastAPI)
- **APScheduler** — планировщик фоновых задач
- **Pydantic Settings** — конфигурация
- **uv** — пакетный менеджер

## Архитектура

Проект построен на **Clean Architecture** с двумя равноправными интерфейсами:

```
Telegram Bot (Aiogram) ─┐
                         ├─→ Interactors → Domain
Web API (FastAPI)      ─┘
```

Один слой бизнес-логики обслуживает оба интерфейса.

### Структура

```
src/
├── apps/
│   ├── user/                          # Домен: пользователи и рефералы
│   │   ├── domain/                    # models, commands, exceptions
│   │   ├── application/               # interactor.py + interfaces/
│   │   ├── adapters/                  # orm.py, gateway.py, view.py
│   │   ├── controllers/bot/           # Aiogram handlers
│   │   ├── controllers/http/          # FastAPI endpoints
│   │   └── ioc.py                     # Dishka Provider
│   └── device/                        # Домен: устройства, подписки, платежи
│       ├── domain/
│       ├── application/
│       ├── adapters/
│       ├── controllers/bot/
│       ├── controllers/http/
│       └── ioc.py
├── common/
│   ├── bot/                           # keyboards, lexicon, cbdata, router
│   └── scheduler/                     # фоновая задача проверки подписок
└── infrastructure/
    ├── config.py                      # AppConfig (Pydantic Settings)
    ├── auth.py                        # заглушка авторизации (X-Telegram-Id)
    └── database/                      # base, uow, provider
ioc.py                                 # корневой Dishka контейнер
main_bot.py                            # точка входа: Telegram Bot
main_web.py                            # точка входа: FastAPI
```

### CQRS

- **Gateway** — только запись, используется в Interactor
- **View** — только чтение, используется в Controller
- **Interactor** — один агрегат, возвращает `{Entity}Info` (frozen dataclass)

### Домены

| Домен | Агрегаты | Interactor методы |
|-------|----------|-------------------|
| `user` | User | `get_or_create`, `get_referral_code`, `add_referral_bonus`, `deduct_balance`, `mark_free_month_used` |
| `device` | Device + Subscription + Payment | `create_device`, `create_device_free`, `delete_device`, `renew_subscription` |

## Установка

```bash
# Клонировать репозиторий
git clone ...
cd vpn

# Установить зависимости
uv sync --extra dev

# Скопировать конфиг
cp .env.example .env
# Заполнить .env своими значениями
```

## Конфигурация

Файл `.env`:

```env
BOT__TOKEN=your_telegram_bot_token
BOT__ADMIN_ID=123456789
BOT__BOT_NAME=MyVpnBot

DATABASE__URL=postgresql+asyncpg://user:pass@localhost:5432/vpn

PAYMENT__PAYMENT_URL=https://your-payment-link
PAYMENT__PAYMENT_QR=qr_code_value
PAYMENT__FREE_MONTH=7
```

## Команды

```bash
# Зависимости
uv sync --extra dev

# Миграции
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "описание"

# Запуск бота
uv run python main_bot.py

# Запуск веб API
uv run uvicorn main_web:app --reload

# Тесты
uv run pytest

# Линтинг
uv run ruff check --fix && uv run ruff format
```

## API

После запуска `main_web.py` доступна документация: `http://localhost:8000/docs`

### Авторизация

Текущая реализация — заглушка: передавай `X-Telegram-Id: <telegram_id>` в заголовке.
Будет заменено на Telegram Login Widget + JWT без изменения бизнес-логики.

### Эндпоинты

```
GET  /api/v1/users/me                    Профиль пользователя
GET  /api/v1/users/referral              Реферальная ссылка

GET  /api/v1/devices/                    Список устройств
POST /api/v1/devices/                    Создать устройство
GET  /api/v1/devices/{device_id}         Детали устройства
DELETE /api/v1/devices/{device_id}       Удалить устройство
POST /api/v1/devices/{device_name}/renew Продлить подписку

GET  /health                             Health check
```

## Тесты

Unit-тесты для Interactor'ов (мок Gateway, без БД):

```bash
uv run pytest tests/unit/ -v
```

## Планировщик

Каждый день в 09:00 (Asia/Yekaterinburg) бот проверяет подписки, истекающие сегодня, и отправляет уведомления пользователям и отчёт администратору.
