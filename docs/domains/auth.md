# Auth

Аутентификация пользователей: OTP по email и вход через бот-токен. Выдаёт JWT (httpOnly cookie + Bearer header).

## Модели

### `OtpCode` (`domain/models.py`)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `int \| None` | PK |
| `email` | `str` | Email получателя |
| `code` | `str` | 6-значный код |
| `created_at` | `datetime` | Время создания |
| `expires_at` | `datetime` | Время истечения (default: +5 минут) |
| `is_used` | `bool` | Использован ли |

### `BotAuthToken` (`domain/models.py`)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `int \| None` | PK |
| `user_id` | `int` | ID пользователя в БД |
| `token` | `str` | UUID hex-токен |
| `created_at` | `datetime` | Время создания |
| `expires_at` | `datetime` | Время истечения (default: +10 минут) |
| `is_used` | `bool` | Использован ли |

## Commands (`domain/commands.py`)

| Команда | Поля | Назначение |
|---------|------|------------|
| `RequestOtp` | `email` | Запросить OTP на email |
| `VerifyOtp` | `email`, `code` | Верифицировать OTP |
| `CreateBotToken` | `user_id` | Создать токен для входа через бота |
| `VerifyBotToken` | `token` | Верифицировать бот-токен |

## Exceptions (`domain/exceptions.py`)

| Исключение | Параметры | Когда |
|------------|-----------|-------|
| `OtpInvalid` | `email` | Неверный OTP-код |
| `OtpExpired` | `email` | OTP истёк |
| `BotTokenInvalid` | `token` | Неверный бот-токен |
| `BotTokenExpired` | `token` | Бот-токен истёк |

## Interactor (`application/interactor.py`)

`AuthInteractor(auth_gateway: AuthGateway, user_gateway: UserGateway, uow: SQLAlchemyUoW, email_sender: EmailSender)`

| Метод | Команда | Возвращает | Логика |
|-------|---------|------------|--------|
| `request_otp` | `RequestOtp` | `None` | Генерирует 6-значный код → сохраняет → отправляет email |
| `verify_otp` | `VerifyOtp` | `AuthResult` | Проверяет код и срок → находит/создаёт юзера по email → возвращает JWT |
| `create_bot_token` | `CreateBotToken` | `str` | Генерирует UUID-токен для входа через бота |
| `verify_bot_token` | `VerifyBotToken` | `AuthResult` | Проверяет токен и срок → возвращает JWT |

## Gateway — запись (`application/interfaces/gateway.py`)

`AuthGateway(Protocol)`

| Метод | Сигнатура |
|-------|-----------|
| `save_otp` | `(otp: OtpCode) -> None` |
| `get_otp` | `(email: str, code: str) -> OtpCode \| None` |
| `mark_otp_used` | `(otp: OtpCode) -> None` |
| `save_bot_token` | `(token: BotAuthToken) -> None` |
| `get_bot_token` | `(token: str) -> BotAuthToken \| None` |
| `mark_bot_token_used` | `(token: BotAuthToken) -> None` |

## EmailSender (`application/interfaces/email_sender.py`)

`EmailSender(Protocol)`

| Метод | Сигнатура |
|-------|-----------|
| `send_otp` | `(email: str, code: str) -> None` |

Реализация: `SmtpService` в `src/infrastructure/smtp.py` (aiosmtplib, Gmail SMTP).

## Info-объекты (результаты)

| Объект | Поля |
|--------|------|
| `AuthResult` | `access_token` (JWT), `user_id` (int) |

## Зависимости от других доменов

- **User**: `AuthInteractor` использует `UserGateway` для поиска/создания пользователя по email
- **Infrastructure**: `create_jwt()` из `src/infrastructure/auth.py`

## Auth flow

```
OTP:   email → request_otp → send email → verify_otp → JWT cookie
Bot:   /web → create_bot_token → ссылка → verify_bot_token → JWT cookie
```

## Файлы

| Файл | Путь |
|------|------|
| Модели | `src/apps/auth/domain/models.py` |
| Команды | `src/apps/auth/domain/commands.py` |
| Исключения | `src/apps/auth/domain/exceptions.py` |
| Interactor | `src/apps/auth/application/interactor.py` |
| Gateway (interface) | `src/apps/auth/application/interfaces/gateway.py` |
| EmailSender (interface) | `src/apps/auth/application/interfaces/email_sender.py` |
| ORM | `src/apps/auth/adapters/orm.py` |
| Gateway (impl) | `src/apps/auth/adapters/gateway.py` |
| HTTP router | `src/apps/auth/controllers/http/router.py` |
| DI provider | `src/apps/auth/ioc.py` |
| SMTP (impl) | `src/infrastructure/smtp.py` |
| JWT utils | `src/infrastructure/auth.py` |
