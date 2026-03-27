# CLAUDE.md — VPN Bot

Локальные правила проекта. Имеют приоритет над глобальным `~/.claude/CLAUDE.md`.

---

## Проект

Telegram VPN-бот + FastAPI веб-интерфейс. Два равноправных интерфейса — один слой бизнес-логики.

---

## Стек

- **Python 3.12+**, **Aiogram 3**, **FastAPI**, **SQLAlchemy 2 async**, **Dishka**, **APScheduler**
- **uv** — пакетный менеджер (не pip, не poetry)
- **ruff** — линтер и форматтер
- **pytest + pytest-asyncio** — тесты

---

## Структура (критически важно знать)

```
src/apps/{domain}/
├── domain/               # models.py, commands.py, exceptions.py — чистый Python
├── application/
│   ├── interactor.py     # use case
│   └── interfaces/
│       ├── gateway.py    # Protocol — запись
│       └── view.py       # Protocol — чтение (+ frozen dataclasses результатов)
├── adapters/             # orm.py, gateway.py, view.py — SQLAlchemy
├── controllers/
│   ├── bot/router.py     # Aiogram handlers
│   └── http/router.py    # FastAPI endpoints (route_class=DishkaRoute)
└── ioc.py                # Dishka Provider

src/common/bot/           # keyboards/, lexicon/, cbdata.py, router.py
src/infrastructure/       # config.py, auth.py, database/
ioc.py                    # корневой контейнер
main_bot.py               # Aiogram + Dishka + APScheduler
main_web.py               # FastAPI + Dishka
```

---

## Ключевые правила

### Interactor
- Принимает `UserGateway` + `SQLAlchemyUoW` через конструктор
- Возвращает только frozen dataclasses (`UserInfo`, `DeviceCreatedInfo`, etc.)
- После каждой записи вызывает `await self._uow.commit()`
- Никогда не импортирует View

### Gateway / View
- `Gateway` — только write, инжектируется в Interactor
- `View` — только read, инжектируется в Controller (никогда в Interactor)

### Bot-контроллеры (Aiogram)
- Зависимости через `FromDishka[T]`
- Только оркестрация: вызовы Interactor'ов и View'ов
- UI state machine (выбор тарифа, подтверждение) — в контроллере, не в Interactor

### HTTP-контроллеры (FastAPI)
- `router = APIRouter(route_class=DishkaRoute)` — обязательно для FromDishka
- `CurrentUser` из `src/infrastructure/auth.py` — авторизация (сейчас заглушка)

### DI (Dishka)
- Два домена: `UserProvider` и `DeviceProvider`
- `DatabaseProvider` — `AsyncEngine` на APP scope, `AsyncSession` на REQUEST scope
- Корневой контейнер собирается в `ioc.py`

---

## Домены

| Домен | Файлы |
|-------|-------|
| `user` | `src/apps/user/` |
| `device` | `src/apps/device/` (включает Subscription + Payment) |

Subscription и Payment не имеют своих Interactor'ов — живут внутри Device.

---

## ORM-модели

Находятся в `src/apps/{domain}/adapters/orm.py`. Alembic смотрит на `src/infrastructure/database/base.Base` и импортирует обе ORM в `alembic/env.py`.

Имена классов: `UserORM`, `DeviceORM`, `SubscriptionORM`, `PaymentORM`.

---

## Команды

```bash
uv sync --extra dev                              # зависимости
uv run pytest tests/unit/ -v                     # unit-тесты
uv run ruff check --fix && uv run ruff format    # линтинг
uv run alembic upgrade head                      # миграции
uv run alembic revision --autogenerate -m "msg"  # новая миграция
uv run python main_bot.py                        # запуск бота
uv run uvicorn main_web:app --reload             # запуск API
```

---

## Что планируется

- Авторизация на сайте: Telegram Login Widget + JWT (заменить `src/infrastructure/auth.py`)
- Redis FSM Storage вместо MemoryStorage в `main_bot.py`
- Панель администратора: `/api/v1/admin/` роутер
- История платежей: `/api/v1/payments/history`
