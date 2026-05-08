# Web API Endpoints

**Точка входа:** `main_web.py`
**Авторизация:** JWT в httpOnly cookie `access_token` или заголовок `Authorization: Bearer <token>`

---

## Device API

**Файл:** `src/apps/device/controllers/http/router.py`

```
GET  /api/v1/devices/
  → list[{id, device_name}]

GET  /api/v1/devices/{device_id}
  → {device_name, end_date (DD.MM.YYYY), amount, payment_date (DD.MM.YYYY)}

POST /api/v1/devices/
  Body: {device_type, period_months, amount}
  → {device_name}

DELETE /api/v1/devices/{device_id}
  → {deleted: device_name}

POST /api/v1/devices/{device_name}/renew
  Body: {period_months, amount}
  → {device_name, end_date (ISO), plan}
```

---

## User API

**Файл:** `src/apps/user/controllers/http/router.py`

```
GET /api/v1/users/me
  → {user_id, telegram_id, balance, referral_code}
  # telegram_id = null для web-only пользователей

GET /api/v1/users/referral
  → {referral_code, referral_link, invited_count}
  # работает для всех пользователей, в т.ч. без Telegram
  # invited_count = 0 для web-only (реферальная система через бот)
```

---

## Cabinet API (web_key)

**Файл:** `src/apps/device/controllers/http/cabinet_router.py`

Авторизация через `web_key` (UUID), генерируется командой `/web` в боте.

```
GET /api/v1/cabinet/{web_key}
  → {
      user: {balance, referral_code},
      subscription: {is_active, end_date, days_left, device_limit, subscription_url} | null,
      hwid_devices: [{hwid, platform, os_version, device_model}]
    }

DELETE /api/v1/cabinet/{web_key}/hwid/{hwid}
  → 204 No Content

DELETE /api/v1/cabinet/{web_key}/hwid
  → 204 No Content (удалить все)
```

---

## Auth API

**Файл:** `src/apps/auth/controllers/http/router.py`

```
POST /api/v1/auth/otp/request
  Body: {email}
  → {detail: "OTP sent to email"}

POST /api/v1/auth/otp/verify
  Body: {email, code}
  → {access_token, user_id}
  Cookie: устанавливает httpOnly access_token

GET /api/v1/auth/bot-token/{token}
  → {access_token, user_id}
  Cookie: устанавливает httpOnly access_token
  # token генерируется командой /web в боте

POST /api/v1/auth/logout
  → {detail: "Logged out"}
  Cookie: удаляет access_token

GET /api/v1/auth/me
  → {user_id}
```

---

## Tariffs API

**Файл:** `src/apps/device/controllers/http/tariffs_router.py`

```
GET /api/v1/tariffs
  → {"1": {"1": 150, "3": 400, "6": 750, "12": 1200},
     "2": {"1": 250, ...},
     "3": {"1": 350, ...}}
  # Без авторизации. Ключи — строки (device_limit → months → price_rub)
```

---

## Payments API

**Файл:** `src/apps/device/controllers/http/payments_router.py`
**Авторизация:** JWT обязательна для всех эндпоинтов.

```
POST /api/v1/payments/initiate
  Body: {action: "new"|"renew", plan: 1|3|6|12, device_limit: 1|2|3}
  → {
      pending_id: int,
      amount: int,         # полная стоимость из TARIFF_MATRIX
      balance_used: int,   # списано с бонусного счёта
      final_amount: int,   # к оплате через YooKassa (0 если баланс покрывает)
      payment_url: str | null  # null если final_amount == 0
    }

POST /api/v1/payments/{pending_id}/confirm
  # Только для balance-only (final_amount == 0) — подтвердить без YooKassa
  # Проверяет ownership (pending принадлежит текущему пользователю)
  → {subscription_url: str | null, end_date: str (ISO)}
  # 404 если не найден или не принадлежит пользователю
  # 400 если статус уже не "pending"

GET /api/v1/payments/history
  → [{id, amount, date (ISO), plan, device_limit, payment_method, status}]
  # Отсортировано по дате DESC

GET /api/v1/payments/{pending_id}/status
  → {status: "pending"|"confirmed"|"rejected",
     subscription_url: str | null,
     end_date: str (ISO) | null}
  # Для polling после редиректа с YooKassa
  # 404 если не найден или не принадлежит пользователю
```

---

## YooKassa Webhook

**Файл:** `src/apps/device/controllers/http/yookassa_router.py`

```
POST /api/v1/payments/yookassa/webhook
  Body: {event: "payment.succeeded", object: {id, amount, metadata: {pending_id}}}
  → {status: "ok" | "error" | ...}
```

> Подробнее о логике вебхука: [flows/payment.md](../flows/payment.md)
