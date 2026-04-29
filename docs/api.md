# HTTP API

Все эндпоинты FastAPI. Точка входа: `main_web.py`. Авторизация: JWT через httpOnly cookie `access_token` или заголовок `Authorization: Bearer <token>`.

## Auth (`/api/v1/auth`)

Router: `src/apps/auth/controllers/http/router.py`

### `POST /api/v1/auth/otp/request`

Запрос OTP-кода на email.

- **Auth**: нет
- **Body**: `{ "email": "user@example.com" }`
- **Response**: `{ "detail": "OTP sent to email" }`
- **Ошибки**: —

### `POST /api/v1/auth/otp/verify`

Верификация OTP. Создаёт пользователя если не существует. Ставит httpOnly cookie.

- **Auth**: нет
- **Body**: `{ "email": "user@example.com", "code": "123456" }`
- **Response**: `{ "access_token": "...", "user_id": 1 }`
- **Cookie**: `access_token` (httpOnly, secure, samesite=lax, max_age=24h)
- **Ошибки**: 400 `Invalid OTP code`, 400 `OTP code expired`

### `GET /api/v1/auth/bot-token/{token}`

Вход через бот-токен (генерируется командой /web в боте). Ставит httpOnly cookie.

- **Auth**: нет
- **Response**: `{ "access_token": "...", "user_id": 1 }`
- **Cookie**: `access_token` (httpOnly, secure, samesite=lax, max_age=24h)
- **Ошибки**: 400 `Invalid token`, 400 `Token expired`

### `POST /api/v1/auth/logout`

Удаление cookie авторизации.

- **Auth**: нет
- **Response**: `{ "detail": "Logged out" }`

### `GET /api/v1/auth/me`

Текущий авторизованный пользователь.

- **Auth**: JWT
- **Response**: `{ "user_id": 1 }`
- **Ошибки**: 401 `Authentication required`

---

## Users (`/api/v1/users`)

Router: `src/apps/user/controllers/http/router.py`

### `GET /api/v1/users/me`

Профиль текущего пользователя.

- **Auth**: JWT
- **Response**: `{ "user_id": 1, "telegram_id": 123456789, "email": "...", "balance": 50, "free_months": false, "referral_code": "abc12345" }`
- **Примечание**: если пользователь без Telegram (зарегистрирован через email), `telegram_id = null`, `balance = 0`

### `GET /api/v1/users/referral`

Реферальная ссылка пользователя.

- **Auth**: JWT
- **Response**: `{ "referral_code": "abc12345", "referral_link": "https://t.me/my7vpnbot?start=abc12345", "invited_count": 3 }`
- **Ошибки**: 400 `Referral system requires Telegram account`

---

## Devices (`/api/v1/devices`)

Router: `src/apps/device/controllers/http/router.py`

### `GET /api/v1/devices/`

Список устройств текущего пользователя.

- **Auth**: JWT
- **Response**: `[{ "id": 1, "device_name": "iOS 12345" }]`

### `GET /api/v1/devices/{device_id}`

Детальная информация об устройстве.

- **Auth**: JWT (не проверяет владельца)
- **Response**: `{ "device_name": "iOS 12345", "end_date": "2025-06-01", "amount": 150, "payment_date": "2025-05-01" }`
- **Ошибки**: 404 `Device not found`

### `POST /api/v1/devices/`

Создание устройства с подпиской и платежом.

- **Auth**: JWT
- **Body**: `{ "device_type": "iOS", "period_months": 3, "amount": 400 }`
- **Response**: `{ "device_name": "iOS 12345" }`
- **Ошибки**: 400 `Telegram account required to create device`

### `DELETE /api/v1/devices/{device_id}`

Удаление устройства.

- **Auth**: JWT
- **Response**: `{ "deleted": "iOS 12345" }`
- **Ошибки**: 404 `Device not found`

### `POST /api/v1/devices/{device_name}/renew`

Продление подписки устройства.

- **Auth**: JWT
- **Body**: `{ "period_months": 3, "amount": 400 }`
- **Response**: `{ "device_name": "iOS 12345", "end_date": "2025-09-01T...", "plan": 3 }`
- **Ошибки**: 404 `Device not found`, 404 `Subscription not found`

---

## Health

### `GET /health`

- **Auth**: нет
- **Response**: `{ "status": "ok" }`

---

## Общее

- Все роутеры используют `route_class=DishkaRoute` для DI
- Авторизация: `CurrentUser` из `src/infrastructure/auth.py` — извлекает `user_id: int` из JWT
- JWT берётся из cookie `access_token` или заголовка `Authorization: Bearer <token>`
- Настройки JWT: `src/infrastructure/config.py` → `AuthSettings`
