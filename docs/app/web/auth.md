# Авторизация (Web)

**Файл:** `src/infrastructure/auth.py`
**Auth domain:** `src/apps/auth/`

---

## Механизм

JWT-токены, хранятся в httpOnly cookie `access_token`.

**Параметры:**
- Алгоритм: `HS256`
- Срок: `app_config.auth.jwt_expire_minutes` (default: 1440 мин = 24 ч)
- Payload: `{"sub": str(user_id), "exp": ..., "iat": ...}`

---

## Способы входа

### 1. OTP по email (для прямого входа в кабинет)
```
POST /api/v1/auth/otp/request  {email}   → отправить код на почту
POST /api/v1/auth/otp/verify   {email, code}  → установить cookie + вернуть JWT
```
OTP хранится в памяти (или Redis — планируется). Срок: `app_config.auth.otp_expire_minutes` (default: 5 мин).

### 2. Bot-token (вход из Telegram-бота)
```
Бот: /web команда → генерирует short-lived token (UUID)
GET /api/v1/auth/bot-token/{token}  → установить cookie + вернуть JWT
```
Срок токена: `app_config.auth.bot_token_expire_minutes` (default: 10 мин).
Хранение: `src/apps/auth/` (в памяти или БД — AuthInteractor).

---

## Dependency Injection (FastAPI)

```python
# src/infrastructure/auth.py
CurrentUser = Annotated[int, Depends(get_current_user_id)]

# В роутерах:
async def endpoint(user_id: CurrentUser):
    ...
```

`get_current_user_id` извлекает и валидирует JWT из cookie или заголовка `Authorization: Bearer`.
При невалидном токене → `401 Unauthorized`.

---

## Текущее состояние

- OTP по email реализован, но SMTP нужно настроить
- Bot-token (вход через /web) — реализован и работает
- Telegram Login Widget — **планируется** (заменит заглушку в auth.py)
- Redis для OTP и FSM Storage — **планируется**

---

## Cabinet API (без полной JWT-авторизации)

Личный кабинет через `web_key` (UUID в `users.web_key`) работает **без JWT**:
```
GET /api/v1/cabinet/{web_key}  → данные пользователя
```
Web-key генерируется командой `/web` в боте (`UserInteractor.get_or_create_web_key()`).
