# Admin Confirm + 3x-ui Integration — Design Spec

## Goal

Заменить немедленное создание устройства при "Я оплатил" на двухшаговый флоу:
пользователь сообщает об оплате → администратор подтверждает → система автоматически
создаёт клиента в 3x-ui и отправляет VLESS-ссылку пользователю.

---

## Context

**Проблема:** Сейчас при нажатии "Я оплатил" устройство создаётся немедленно без проверки.
Администратор получает только информационное уведомление. Выдача VPN-ключа полностью ручная
(зайти в 3x-ui, добавить клиента, отправить ссылку).

**Решение:** Ввести промежуточное состояние `PendingPayment` в БД. Администратор получает
уведомление с кнопками [✅ Подтвердить] [❌ Отклонить]. При подтверждении — система сама
создаёт клиента в 3x-ui и доставляет VLESS-ссылку.

---

## User Flow

```
User: нажимает "Я оплатил ✅"
  → сохраняем PendingPayment в БД
  → user: "⏳ Ожидайте подтверждения оплаты администратором"
  → admin: уведомление с деталями + кнопки [✅ Подтвердить] [❌ Отклонить]

Admin: нажимает ✅ Подтвердить
  → читаем PendingPayment
  → create_device() или renew_subscription() в БД
  → XuiClient.add_client(device_name) → VLESS-ссылка (только для new, не для renew)
  → сохраняем vpn_config в Device
  → user сообщение 1: "✅ Оплата подтверждена! Ключ готов 👇"
  → user сообщение 2: `vless://...` (code block, легко скопировать)
  → user сообщение 3 (опционально): кнопка [📋 Инструкция по подключению]
  → admin: "✅ Ключ выдан: {device_name}"
  → удаляем PendingPayment

Admin: нажимает ❌ Отклонить
  → user: "❌ Оплата не подтверждена. Обратитесь @my7vpnadmin"
  → admin: "Отклонено"
  → удаляем PendingPayment

Продление (renew):
  → тот же флоу через PendingPayment
  → при подтверждении: renew_subscription() в БД
  → 3x-ui НЕ трогаем (клиент там уже есть, ключ работает)
  → user получает подтверждение без нового ключа
```

---

## Architecture

### Новые компоненты

```
src/infrastructure/xui/
  __init__.py
  client.py                     # XuiClient

src/apps/device/domain/
  models.py                     # + PendingPayment dataclass

src/apps/device/adapters/
  orm.py                        # + PendingPaymentORM
  gateway.py                    # + save/get/delete методы

src/apps/device/application/
  interfaces/gateway.py         # + PendingPaymentGateway Protocol
  interactor.py                 # + confirm_payment(), reject_payment()

src/common/bot/cbdata.py        # + AdminConfirmCallback

src/apps/device/controllers/bot/router.py  # изменить шаги 6a/6b, добавить admin handlers
```

### Изменённые компоненты

```
src/infrastructure/config.py    # + XuiSettings
.env                            # + XUI_* переменные
alembic/versions/               # новая миграция для PendingPaymentORM
```

---

## Domain Model

### PendingPayment (dataclass)

```python
@dataclass
class PendingPayment:
    user_telegram_id: int       # кому выдавать ключ
    action: str                 # "new" | "renew"
    device_type: str            # "Android", "iOS", "TV", "Windows", "MacOS"
    device_name: str | None     # для renew — имя существующего устройства
    duration: int               # месяцев
    amount: int                 # сумма к оплате (уже с вычетом баланса)
    balance_to_deduct: int      # сколько списать с баланса при подтверждении
    created_at: datetime
    id: int | None = None
```

### PendingPaymentORM (SQLAlchemy)

Таблица `pending_payments`:
- `id` — Integer, PK, autoincrement
- `user_telegram_id` — BigInteger, not null
- `action` — String(10), not null
- `device_type` — String(20), not null
- `device_name` — String(100), nullable
- `duration` — Integer, not null
- `amount` — Integer, not null
- `balance_to_deduct` — Integer, not null, default 0
- `created_at` — DateTime(timezone=True), not null

---

## Callback Data

```python
class AdminConfirmCallback(CallbackData, prefix="adm"):
    pending_id: int
    action: str   # "confirm" | "reject"
```

---

## 3x-ui Integration

### XuiSettings (в config.py)

```python
class XuiSettings(BaseModel):
    url: str                # https://myserver.com:54321
    username: str           # admin логин панели
    password: str           # admin пароль панели
    inbound_id: int         # ID инбаунда VLESS в 3x-ui
    vless_template: str     # шаблон: "vless://{uuid}@host:port?params#{name}"
```

В `.env`:
```
XUI__URL=http://62.133.60.207:57385/vps7my
XUI__USERNAME=admin
XUI__PASSWORD=secret
XUI__INBOUND_ID=1
XUI__VLESS_TEMPLATE=vless://{uuid}@62.133.60.207:443/?type=grpc&serviceName=&authority=&security=reality&pbk=veL6JjshQunKETu6Rr0WNfE6rUT7tOQncje7Qc2x8mc&fp=chrome&sni=kicker.de&sid=278e&spx=%2F#{name}
```

**Доступ к панели:**
- Бот-сервер обращается напрямую по IP после открытия порта на VPN-сервере:
  `ufw allow from <BOT_SERVER_IP> to any port 57385`
- Админ заходит через SSH-туннель как раньше — не конфликтует

### XuiClient (src/infrastructure/xui/client.py)

```python
class XuiClient:
    async def add_client(self, client_name: str) -> str:
        """
        1. POST /login — получить сессию
        2. POST /panel/api/inbounds/addClient — добавить клиента
           - генерируем UUID сами (uuid.uuid4())
           - имя клиента = device_name (уже уникальное)
        3. Подставить UUID + name в vless_template
        4. Вернуть готовую VLESS-ссылку
        """
```

Сессионная кука живёт на время одного вызова `add_client` (логин → операция → готово).
Никакого хранения сессии между вызовами — проще и безопаснее.

---

## Bot Handler Changes

### Шаги 6a (new) и 6b (renew) в handle_vpn_flow

**Было:**
```python
result = await interactor.create_device(...)   # сразу создаём
await bot.send_message(ADMIN_ID, "новое устройство")  # только инфо
```

**Станет:**
```python
pending = await interactor.create_pending_payment(CreatePendingPayment(...))
await call.message.answer("⏳ Ожидайте подтверждения оплаты администратором")
await bot.send_message(ADMIN_ID,
    text=f"💳 Новый платёж!\n👤 @{username}\n📱 {device_type}\n📅 {duration} мес → {amount}₽",
    reply_markup=admin_confirm_keyboard(pending.id)
)
```

### Новые admin handlers

```python
@router.callback_query(AdminConfirmCallback.filter(F.action == "confirm"))
async def handle_admin_confirm(call, callback_data, bot, interactor):
    # 1. load pending
    # 2. create_device() или renew_subscription()
    # 3. если new: xui_client.add_client(device_name) → vless_link
    # 4. сохранить vpn_config в device
    # 5. отправить пользователю 2 сообщения
    # 6. удалить pending

@router.callback_query(AdminConfirmCallback.filter(F.action == "reject"))
async def handle_admin_reject(call, callback_data, bot, interactor):
    # 1. load pending
    # 2. notify user
    # 3. delete pending
```

### Доставка ключа пользователю (action=new)

```
Сообщение 1: "✅ Оплата подтверждена! Ключ готов 👇"
Сообщение 2: `vless://uuid@server:443?...#Android_1234`   ← code block
+ кнопка [📋 Инструкция по подключению]
```

### Доставка при продлении (action=renew)

```
Сообщение 1: "✅ Оплата подтверждена! Подписка продлена до {end_date}."
```
Ключ не высылается повторно — у пользователя он уже есть.

---

## Interactor Changes

### Новые методы DeviceInteractor

```python
async def create_pending_payment(self, cmd: CreatePendingPayment) -> PendingPaymentInfo:
    """Сохранить запись об ожидающем платеже."""

async def confirm_payment(self, cmd: ConfirmPayment) -> ConfirmPaymentResult:
    """
    - load PendingPayment
    - если new: create_device() + xui
    - если renew: renew_subscription()
    - удалить PendingPayment
    - вернуть device_name, vless_link (None для renew), end_date
    """

async def reject_payment(self, cmd: RejectPayment) -> PendingPaymentInfo:
    """Load + delete PendingPayment, вернуть user_telegram_id для уведомления."""
```

`XuiClient` инжектируется в `DeviceInteractor` через Dishka.

---

## DI (Dishka)

`XuiClient` регистрируется в `DeviceProvider` с `Scope.APP` (singleton — один клиент на всё приложение).

---

## Out of Scope

- QR-код для VLESS-ссылки
- Автоматическое отключение клиента в 3x-ui при истечении подписки
- Веб-интерфейс для пользователей без Telegram
- Интеграция с платёжным шлюзом
