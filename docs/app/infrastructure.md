# Infrastructure

---

## Remnawave API

**HTTP-клиент:** `src/infrastructure/remnawave/client.py` → `RemnawaveClient`
**Gateway-адаптер:** `src/apps/device/adapters/remnawave_gateway.py`
**Интерфейс:** `src/apps/device/application/interfaces/remnawave_gateway.py` → `RemnawaveGateway`

### Методы клиента

| Метод | HTTP | Назначение |
|-------|------|-----------|
| `create_user(telegram_id, expire_at, device_limit)` | POST /api/users | Создать аккаунт VPN |
| `update_user(uuid, expire_at, device_limit)` | PATCH /api/users | Продлить/изменить |
| `delete_user(uuid)` | DELETE /api/users/{uuid} | Удалить аккаунт |
| `get_user_by_telegram_id(telegram_id)` | GET /api/users/by-telegram-id/{id} | Найти по telegram_id |
| `enable_user(uuid)` | POST /api/users/{uuid}/actions/enable | Включить |
| `disable_user(uuid)` | POST /api/users/{uuid}/actions/disable | Выключить |
| `get_hwid_devices_count(uuid)` | GET /api/hwid/devices/{uuid} | Кол-во подключений |
| `get_hwid_devices(uuid)` | GET /api/hwid/devices/{uuid} | Список устройств |
| `delete_hwid_device(uuid, hwid)` | POST /api/hwid/devices/delete | Удалить одно |
| `delete_all_hwid_devices(uuid)` | POST /api/hwid/devices/delete-all | Удалить все |

### Создание пользователя

```python
payload = {
    "username": f"tg{telegram_id}",    # формат имён в панели
    "expireAt": "YYYY-MM-DDTHH:MM:SS.000Z",
    "hwidDeviceLimit": device_limit,
    "telegramId": telegram_id,
    "trafficLimitBytes": 0,             # безлимит
    "activeInternalSquads": [default_squad_uuid],  # если настроен
}
```

### Возвращаемые данные (RemnawaveUserInfo)

```python
RemnawaveUserInfo:
    uuid: str
    username: str
    subscription_url: str   # ссылка для приложений (VLESS/etc)
    expire_at: str          # ISO datetime
    status: str             # "ACTIVE" | "DISABLED" | etc
    hwid_device_limit: int
    telegram_id: int | None
```

---

## YooKassa

**Клиент:** `src/infrastructure/yookassa/client.py` → `YooKassaClient`
**Конфиг:** `app_config.yookassa` (`shop_id`, `secret_key`, `return_url`, `enabled`)

```python
# Создать платёж
payment = await client.create_payment(amount=300, pending_id=42)
# → CreatedPayment(payment_id="...", confirmation_url="https://...")

# Проверить статус (в вебхуке)
status = await client.get_payment_status("payment_id_here")
# → "pending" | "succeeded" | "canceled"
```

Вебхук: `POST /api/v1/payments/yookassa/webhook`

---

## YuMoney (legacy)

**Файл:** `src/infrastructure/yumoney/quickpay.py`
**Конфиг:** `app_config.yumoney` (`wallet`, `notification_secret`, `success_url`, `enabled`)

```python
url = build_quickpay_url(settings, amount=300, pending_id=42)
# → строит URL для формы оплаты YuMoney

ok = verify_notification_signature(secret, notification_type, ..., received_hash)
# → True если подпись SHA1 верна
```

---

## Scheduler (APScheduler)

**Файл:** `src/common/scheduler/tasks.py`
**Регистрация:** `main_bot.py`

### Задача: send_expiry_notifications

Запускается периодически (cron). Что делает:
1. Найти подписки, истекающие через **7, 3, 1, 0** дней
2. Проверить через `notification_log` — не отправляли ли уже
3. Отправить каждому пользователю напоминание с кнопкой "🔄 Продлить"
4. Записать в `notification_log`
5. Отправить отчёт админу

**Таблица notification_log (ORM):**
```
UNIQUE(user_id, days_before, sub_end_date)
```
Защита от дублирования уведомлений.

---

## Config (src/infrastructure/config.py)

```python
class AppConfig:
    db: DatabaseSettings          # url
    bot: BotSettings              # token, bot_name, admin_id, admin_username
    payment: PaymentSettings      # payment_url, payment_qr, free_month (дни)
    auth: AuthSettings            # jwt_secret, jwt_expire_minutes, site_url, etc.
    smtp: SmtpSettings            # для OTP (email auth)
    remnawave: RemnawaveSettings  # url, token, default_squad_uuid
    yumoney: YuMoneySettings      # wallet, notification_secret, enabled
    yookassa: YooKassaSettings    # shop_id, secret_key, return_url, enabled
    logging: LoggingSettings      # log_level, log_json, log_to_file, etc.
```

**Загружается из переменных окружения через `pydantic-settings`.**

---

## База данных

**ORM:** SQLAlchemy 2 async (`AsyncSession`)
**Миграции:** Alembic (`alembic/`)
**Base:** `src/infrastructure/database/base.py`

Alembic импортирует ORM-модели в `alembic/env.py`:
- `src/apps/user/adapters/orm`
- `src/apps/device/adapters/orm`

---

## DI (Dishka)

**Корневой контейнер:** `ioc.py`

| Провайдер | Файл | Scope |
|-----------|------|-------|
| `DatabaseProvider` | `ioc.py` | `AsyncEngine` = APP, `AsyncSession` = REQUEST |
| `UserProvider` | `src/apps/user/ioc.py` | REQUEST |
| `DeviceProvider` | `src/apps/device/ioc.py` | REQUEST |

Aiogram: `FromDishka[T]` в handler-функциях.
FastAPI: `router = APIRouter(route_class=DishkaRoute)` + `FromDishka[T]` в параметрах.
