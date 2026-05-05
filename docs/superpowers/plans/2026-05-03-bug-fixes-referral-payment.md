# Bug Fixes: Referral, Subscription Display, Payment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Исправить 6 багов в боте — уведомление реферера, тексты экрана друзей, хардкод дней, отображение истёкшей подписки, детали в уведомлении админа, удаление ручного платёжного флоу.

**Architecture:** Каждый фикс изолирован в одном-двух файлах. Нет новых сущностей, нет новых таблиц, нет миграций. Фиксы 1–5 — точечные правки. Фикс 6 — удаление мёртвого кода.

**Tech Stack:** Python 3.12, Aiogram 3, SQLAlchemy async, Dishka, Pydantic

---

## Task 1 — Fix 1: Уведомление реферера при активации бесплатного периода

**Files:**
- Modify: `src/apps/device/controllers/bot/router.py` (~строка 204, после `bot.send_message(chat_id=ADMIN_ID, ...)`)

- [ ] **Step 1: Добавить уведомление реферера**

В `router.py`, в блоке `if action == VpnAction.REFERRAL:`, после блока `await bot.send_message(chat_id=ADMIN_ID, ...)` вставить:

```python
        if referral_id is not None:
            try:
                await bot.send_message(
                    chat_id=referral_id,
                    text="🎉 Твой друг активировал бесплатный период по твоей реферальной ссылке!",
                )
            except Exception:
                log.warning("referral_notify_referrer_failed", referral_id=referral_id)
```

- [ ] **Step 2: Проверить ruff**

```bash
uv run ruff check --fix src/apps/device/controllers/bot/router.py
```

- [ ] **Step 3: Commit**

```bash
git add src/apps/device/controllers/bot/router.py
git commit -m "fix: notify referrer when invited user activates free period"
```

---

## Task 2 — Fix 2: Переименовать "Заработано" → "Ожидаемый бонус"

**Files:**
- Modify: `src/common/bot/lexicon/text_manager.py` (~строка 152, метод `get_friends_screen`)

- [ ] **Step 1: Заменить строку в `get_friends_screen`**

Найти:
```python
            f"Заработано: <b>{total_earned}₽</b>\n"
```

Заменить на:
```python
            f"🎁 Ожидаемый бонус: <b>{total_earned}₽</b> (придёт на баланс когда друг оплатит подписку)\n"
```

- [ ] **Step 2: Проверить ruff**

```bash
uv run ruff check --fix src/common/bot/lexicon/text_manager.py
```

- [ ] **Step 3: Commit**

```bash
git add src/common/bot/lexicon/text_manager.py
git commit -m "fix: rename 'Заработано' to 'Ожидаемый бонус' with clarification on friends screen"
```

---

## Task 3 — Fix 3: Хардкод "5 дней" → из конфига

**Files:**
- Modify: `src/common/bot/lexicon/text_manager.py` (методы `get_main_menu_active` ~строка 6, `get_friends_screen` ~строка 146)
- Modify: `src/apps/user/controllers/bot/router.py` (call sites `get_main_menu_active`, `get_friends_screen`)

- [ ] **Step 1: Добавить параметр `free_days: int` в `get_main_menu_active`**

Найти сигнатуру:
```python
    def get_main_menu_active(user_name: str, end_date: str, used: int, limit: int, balance: int) -> str:
```

Заменить на:
```python
    def get_main_menu_active(user_name: str, end_date: str, used: int, limit: int, balance: int, free_days: int = 5) -> str:
```

Найти в теле метода:
```python
            f"Друг получит 5 дней бесплатно.\n\n"
```

Заменить на:
```python
            f"Друг получит {free_days} дней бесплатно.\n\n"
```

- [ ] **Step 2: Добавить параметр `free_days: int` в `get_friends_screen`**

Найти сигнатуру:
```python
    def get_friends_screen(invited_count: int, total_earned: int, balance: int, referral_link: str) -> str:
```

Заменить на:
```python
    def get_friends_screen(invited_count: int, total_earned: int, balance: int, referral_link: str, free_days: int = 5) -> str:
```

Найти в теле метода:
```python
            f"Ты получаешь <b>50₽</b>, друг — <b>5 дней VPN бесплатно</b>\n\n"
```

Заменить на:
```python
            f"Ты получаешь <b>50₽</b>, друг — <b>{free_days} дней VPN бесплатно</b>\n\n"
```

- [ ] **Step 3: Передать `free_days` в call sites в `user/controllers/bot/router.py`**

В `handle_start` и `handle_start_callback` — все вызовы `bot_repl.get_main_menu_active(...)` дополнить аргументом:
```python
bot_repl.get_main_menu_active(
    ...,
    free_days=app_config.payment.free_month,
)
```

В `handle_friends` и `handle_invite` — вызов `bot_repl.get_friends_screen(...)` дополнить:
```python
bot_repl.get_friends_screen(
    stats.invited_count, stats.total_earned, stats.balance, referral_link,
    free_days=app_config.payment.free_month,
)
```

- [ ] **Step 4: Проверить ruff**

```bash
uv run ruff check --fix src/common/bot/lexicon/text_manager.py src/apps/user/controllers/bot/router.py
```

- [ ] **Step 5: Commit**

```bash
git add src/common/bot/lexicon/text_manager.py src/apps/user/controllers/bot/router.py
git commit -m "fix: replace hardcoded '5 days' with free_month from config"
```

---

## Task 4 — Fix 4: Истёкшая подписка показывает отрицательные дни

**Files:**
- Modify: `src/apps/device/adapters/view.py` (метод `get_subscription_info`, оба запроса)

- [ ] **Step 1: Добавить импорт `datetime` и `UTC`**

В начале `view.py` добавить (если нет):
```python
from datetime import UTC, datetime
```

- [ ] **Step 2: Добавить фильтр в запрос новой модели (`user_subscriptions`)**

Найти в методе `get_subscription_info`:
```python
            .where(UserSubscriptionORM.is_active.is_(True))
```

После этой строки добавить:
```python
            .where(UserSubscriptionORM.end_date > datetime.now(UTC))
```

- [ ] **Step 3: Добавить фильтр в legacy fallback (`subscriptions`)**

Найти:
```python
            .where(SubscriptionORM.is_active.is_(True))
```

После этой строки добавить:
```python
            .where(SubscriptionORM.end_date > datetime.now(UTC))
```

- [ ] **Step 4: Проверить ruff**

```bash
uv run ruff check --fix src/apps/device/adapters/view.py
```

- [ ] **Step 5: Commit**

```bash
git add src/apps/device/adapters/view.py
git commit -m "fix: exclude expired subscriptions from get_subscription_info view"
```

---

## Task 5 — Fix 5: Детали платежа в уведомлении админа (YooKassa)

**Files:**
- Modify: `src/apps/device/application/interactor.py` (датакласс `ConfirmPaymentResult`, метод `confirm_payment`)
- Modify: `src/apps/device/controllers/http/yookassa_router.py` (текст уведомления админа)

- [ ] **Step 1: Добавить поля в `ConfirmPaymentResult`**

Найти:
```python
@dataclass(frozen=True)
class ConfirmPaymentResult:
    user_telegram_id: int
    device_name: str
    action: str  # "new" | "renew"
    subscription_url: str | None
    end_date: datetime
    referrer_telegram_id: int | None = None
```

Заменить на:
```python
@dataclass(frozen=True)
class ConfirmPaymentResult:
    user_telegram_id: int
    device_name: str
    action: str  # "new" | "renew"
    subscription_url: str | None
    end_date: datetime
    amount: int = 0
    duration: int = 0
    device_limit: int = 1
    referrer_telegram_id: int | None = None
```

- [ ] **Step 2: Заполнить новые поля в возврате `confirm_payment`**

Найти в конце метода `confirm_payment`:
```python
        return ConfirmPaymentResult(
            user_telegram_id=pending.user_telegram_id,
            device_name="vpn",
            action=pending.action,
            subscription_url=user.subscription_url,
            end_date=end_date,
            referrer_telegram_id=referrer_telegram_id,
        )
```

Заменить на:
```python
        return ConfirmPaymentResult(
            user_telegram_id=pending.user_telegram_id,
            device_name="vpn",
            action=pending.action,
            subscription_url=user.subscription_url,
            end_date=end_date,
            amount=pending.amount,
            duration=pending.duration,
            device_limit=pending.device_limit,
            referrer_telegram_id=referrer_telegram_id,
        )
```

- [ ] **Step 3: Обновить уведомление админа в `yookassa_router.py`**

Найти:
```python
    end_str = result.end_date.strftime("%d.%m.%Y")
    action_label = "Новая подписка" if result.action == "new" else "Продление"
    await bot.send_message(
        chat_id=app_config.bot.admin_id,
        text=(
            f"✅ ЮKassa автоплатёж\n"
            f"👤 {result.user_telegram_id} | 📱 {result.device_name}\n"
            f"{action_label} до {end_str}\n"
            f"payment_id: {payment_id}"
        ),
    )
```

Заменить на:
```python
    end_str = result.end_date.strftime("%d.%m.%Y")
    action_label = "Новая подписка" if result.action == "new" else "Продление"
    await bot.send_message(
        chat_id=app_config.bot.admin_id,
        text=(
            f"✅ ЮKassa автоплатёж\n"
            f"👤 {result.user_telegram_id}\n"
            f"{action_label} до {end_str}\n"
            f"📱 Устройств: {result.device_limit} | 📅 {result.duration} мес | 💳 {result.amount}₽\n"
            f"payment_id: {payment_id}"
        ),
    )
```

- [ ] **Step 4: Проверить ruff**

```bash
uv run ruff check --fix src/apps/device/application/interactor.py src/apps/device/controllers/http/yookassa_router.py
```

- [ ] **Step 5: Commit**

```bash
git add src/apps/device/application/interactor.py src/apps/device/controllers/http/yookassa_router.py
git commit -m "fix: add amount, duration, device_limit to admin YooKassa notification"
```

---

## Task 6 — Fix 6: Удалить ручной платёжный флоу (QR + admin confirm/reject)

**Files:**
- Modify: `src/apps/device/controllers/bot/router.py`
- Modify: `src/common/bot/cbdata.py`
- Modify: `src/common/bot/keyboards/keyboards.py`
- Modify: `src/common/bot/keyboards/user_actions.py`
- Modify: `src/infrastructure/config.py`

- [ ] **Step 1: Удалить из импортов `router.py`**

Удалить из импортов:
- `RejectPayment` из `src.apps.device.domain.commands`
- `AdminConfirmCallback` из `src.common.bot.cbdata`
- `get_photo_for_pay` из `src.common.bot.files`
- `get_keyboard_admin_confirm`, `get_keyboard_approve_payment_or_cancel` из `src.common.bot.keyboards.keyboards`
- `PaymentStatus` из `src.common.bot.keyboards.user_actions`

Удалить строку:
```python
LINK = app_config.payment.payment_url
```

- [ ] **Step 2: Удалить функцию `_show_qr_payment` целиком**

Удалить всю функцию `_show_qr_payment` (от `async def _show_qr_payment` до конца её тела, включая пустые строки).

- [ ] **Step 3: Удалить `payment_status` из `handle_vpn_flow`**

Удалить строку:
```python
    payment_status = callback_data.payment_status
```

Найти в шаге 4:
```python
    if choice == ChoiceType.NO or payment_status == PaymentStatus.FAILED:
```
Заменить на:
```python
    if choice == ChoiceType.NO:
```

- [ ] **Step 4: Удалить вызов `_show_qr_payment` из шага 5**

В блоке `if choice == ChoiceType.YES:` найти и удалить ветку `else` после `if app_config.yookassa.enabled:`:
```python
        await _show_qr_payment(
            call,
            action,
            "vpn",
            device_limit or 1,
            duration,
            referral_id,
            payment,
            balance,
        )
        await call.answer()
        return
```

- [ ] **Step 5: Удалить шаги 6a и 6b**

Удалить целиком блок:
```python
    # Шаг 6a: новая подписка — оплата заявлена, ждём подтверждения админа
    if action == CallbackAction.NEW_SUB and payment_status == PaymentStatus.SUCCESS:
        ...
```

Удалить целиком блок:
```python
    # Шаг 6b: продление — ждём подтверждения админа
    if action == VpnAction.RENEW and payment_status == PaymentStatus.SUCCESS:
        ...
```

- [ ] **Step 6: Удалить `handle_admin_confirm` и `handle_admin_reject`**

Удалить оба хендлера целиком (декораторы + функции).

- [ ] **Step 7: Почистить `cbdata.py`**

Удалить из `VpnCallback`:
```python
    payment_status: PaymentStatus | None = None
```

Удалить импорт `PaymentStatus` из строки:
```python
from src.common.bot.keyboards.user_actions import ChoiceType, PaymentStatus, VpnAction
```
→ оставить:
```python
from src.common.bot.keyboards.user_actions import ChoiceType, VpnAction
```

Удалить весь класс `AdminConfirmCallback`.

- [ ] **Step 8: Почистить `keyboards.py`**

Удалить функции `get_keyboard_approve_payment_or_cancel` и `get_keyboard_admin_confirm` целиком.

Удалить из импортов:
- `AdminConfirmCallback` из `src.common.bot.cbdata`
- `PaymentStatus` из `src.common.bot.keyboards.user_actions`

- [ ] **Step 9: Почистить `user_actions.py`**

Удалить класс `PaymentStatus` целиком.

Из `ChoiceType` удалить:
```python
    STOP = "stop"
```

- [ ] **Step 10: Почистить `config.py`**

Найти:
```python
class PaymentSettings(BaseModel):
    payment_url: str
    payment_qr: str
    free_month: int
```

Заменить на:
```python
class PaymentSettings(BaseModel):
    free_month: int
```

- [ ] **Step 11: Проверить ruff и что модуль импортируется**

```bash
uv run ruff check --fix \
  src/apps/device/controllers/bot/router.py \
  src/common/bot/cbdata.py \
  src/common/bot/keyboards/keyboards.py \
  src/common/bot/keyboards/user_actions.py \
  src/infrastructure/config.py
```

```bash
uv run python -c "from src.apps.device.controllers.bot.router import router; print('OK')"
uv run python -c "from src.infrastructure.config import app_config; print('OK')"
```

- [ ] **Step 12: Commit**

```bash
git add \
  src/apps/device/controllers/bot/router.py \
  src/common/bot/cbdata.py \
  src/common/bot/keyboards/keyboards.py \
  src/common/bot/keyboards/user_actions.py \
  src/infrastructure/config.py
git commit -m "fix: remove unreachable manual QR payment flow (admin confirm/reject)"
```
