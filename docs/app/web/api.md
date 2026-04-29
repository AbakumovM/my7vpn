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
  → {user_id, telegram_id, email, balance, free_months, referral_code}

GET /api/v1/users/referral
  → {referral_code, referral_link, invited_count}
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

## YooKassa Webhook

**Файл:** `src/apps/device/controllers/http/yookassa_router.py`

```
POST /api/v1/payments/yookassa/webhook
  Body: {event: "payment.succeeded", object: {id, amount, metadata: {pending_id}}}
  → {status: "ok" | "error" | ...}
```

> Подробнее о логике вебхука: [flows/payment.md](../flows/payment.md)
