# Bot UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Переработать UX бота: подписочная модель вместо устройств, новое главное меню (сетка 2×2), упрощённый флоу покупки (3 шага вместо 4), инструкции для happ, реферальный экран со статистикой.

**Architecture:** Изменения затрагивают 3 слоя: data (новые view-методы), UI (клавиатуры + тексты), controllers (роутеры бота). Бизнес-логика (interactors) не меняется. Основной подход — переписать keyboards и text_manager, затем обновить роутеры.

**Tech Stack:** Python 3.12, Aiogram 3, SQLAlchemy 2 async, Dishka DI, pytest

**Spec:** `docs/superpowers/specs/2026-04-24-bot-ux-redesign.md`

---

### Task 1: Config — добавить admin_username

**Files:**
- Modify: `src/infrastructure/config.py`

Сейчас в текстах захардкожен `@my7vpnadmin`. Для URL-кнопки «💬 Поддержка» нужен конфигурируемый username.

- [ ] **Step 1: Добавить `admin_username` в BotSettings**

В `src/infrastructure/config.py` добавить поле:

```python
class BotSettings(BaseModel):
    token: str
    bot_name: str
    admin_id: int
    admin_username: str = "my7vpnadmin"  # без @, для URL t.me/{admin_username}
```

- [ ] **Step 2: Проверить импорт**

```bash
uv run python -c "from src.infrastructure.config import app_config; print(app_config.bot.admin_username)"
```

Expected: `my7vpnadmin`

- [ ] **Step 3: Commit**

```bash
git add src/infrastructure/config.py
git commit -m "feat: add admin_username to BotSettings"
```

---

### Task 2: Data layer — get_subscription_info и get_referral_stats

**Files:**
- Modify: `src/apps/user/application/interfaces/view.py`
- Modify: `src/apps/user/adapters/view.py`
- Modify: `src/apps/device/application/interfaces/view.py`
- Modify: `src/apps/device/adapters/view.py`
- Create: `tests/unit/user/test_referral_stats_view.py`

#### 2.1: SubscriptionInfo в DeviceView

- [ ] **Step 1: Добавить dataclass и метод в Protocol**

В `src/apps/device/application/interfaces/view.py` добавить:

```python
@dataclass(frozen=True)
class SubscriptionInfo:
    end_date: datetime | None
    device_limit: int
    last_payment_amount: int | None
    subscription_url: str | None
```

И метод в `DeviceView`:

```python
class DeviceView(Protocol):
    # ... существующие методы ...

    async def get_subscription_info(self, telegram_id: int) -> SubscriptionInfo | None: ...
```

- [ ] **Step 2: Реализовать в SQLAlchemyDeviceView**

В `src/apps/device/adapters/view.py` добавить метод:

```python
async def get_subscription_info(self, telegram_id: int) -> SubscriptionInfo | None:
    # Получаем последнее устройство пользователя с подпиской
    result = await self._session.execute(
        select(
            SubscriptionORM.end_date,
            DeviceORM.device_limit,
            UserORM.subscription_url,
        )
        .join(DeviceORM, SubscriptionORM.device_id == DeviceORM.id)
        .join(UserORM, DeviceORM.user_id == UserORM.id)
        .where(UserORM.telegram_id == telegram_id)
        .where(SubscriptionORM.is_active.is_(True))
        .order_by(SubscriptionORM.end_date.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None

    # Последний платёж
    payment_result = await self._session.execute(
        select(PaymentORM.amount)
        .join(SubscriptionORM, PaymentORM.subscription_id == SubscriptionORM.id)
        .join(DeviceORM, SubscriptionORM.device_id == DeviceORM.id)
        .join(UserORM, DeviceORM.user_id == UserORM.id)
        .where(UserORM.telegram_id == telegram_id)
        .order_by(PaymentORM.payment_date.desc())
        .limit(1)
    )
    last_amount = payment_result.scalar_one_or_none()

    return SubscriptionInfo(
        end_date=row.end_date,
        device_limit=row.device_limit,
        last_payment_amount=last_amount,
        subscription_url=row.subscription_url,
    )
```

Добавить импорт `SubscriptionInfo` в блок импортов view.py.

- [ ] **Step 3: Проверить импорт**

```bash
uv run python -c "from src.apps.device.adapters.view import SQLAlchemyDeviceView; print('OK')"
```

#### 2.2: ReferralStats в UserView

- [ ] **Step 4: Добавить dataclass и метод в Protocol**

В `src/apps/user/application/interfaces/view.py` добавить:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ReferralStats:
    invited_count: int
    total_earned: int
    balance: int
```

И метод:

```python
class UserView(Protocol):
    # ... существующие методы ...

    async def get_referral_stats(self, telegram_id: int) -> ReferralStats: ...
```

- [ ] **Step 5: Реализовать в SQLAlchemyUserView**

В `src/apps/user/adapters/view.py` добавить:

```python
from src.apps.user.application.interfaces.view import ReferralStats
```

И метод:

```python
async def get_referral_stats(self, telegram_id: int) -> ReferralStats:
    # Сколько пользователей пришло по реферальной ссылке
    count_result = await self._session.execute(
        select(func.count(UserORM.id)).where(UserORM.referred_by == telegram_id)
    )
    invited_count = count_result.scalar_one() or 0

    # Баланс
    balance_result = await self._session.execute(
        select(UserORM.balance).where(UserORM.telegram_id == telegram_id)
    )
    balance = balance_result.scalar_one_or_none() or 0

    return ReferralStats(
        invited_count=invited_count,
        total_earned=invited_count * 50,
        balance=balance,
    )
```

- [ ] **Step 6: Проверить импорт**

```bash
uv run python -c "from src.apps.user.adapters.view import SQLAlchemyUserView; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
git add src/apps/user/application/interfaces/view.py src/apps/user/adapters/view.py \
  src/apps/device/application/interfaces/view.py src/apps/device/adapters/view.py
git commit -m "feat: add get_subscription_info and get_referral_stats to views"
```

---

### Task 3: Keyboards — новые макеты

**Files:**
- Modify: `src/common/bot/keyboards/keyboards.py`
- Modify: `src/common/bot/keyboards/user_actions.py`
- Modify: `src/common/bot/lexicon/lexicon.py`

#### 3.1: Обновить lexicon.py

- [ ] **Step 1: Переписать LEXICON_INLINE_RU и LEXICON_COMMANDS_RU**

Заменить содержимое `src/common/bot/lexicon/lexicon.py`:

```python
from src.common.bot.keyboards.user_actions import CallbackAction, DeviceType

LEXICON_COMMANDS_RU: dict[str, str] = {
    "start": "🏠 Главное меню",
    "invite": "👫 Пригласить друга",
    "help": "📖 Инструкция",
}

LEXICON_INLINE_RU: dict[str, str] = {
    CallbackAction.MY_SUBSCRIPTION: "📋 Подписка",
    CallbackAction.RENEW_SUB: "🔄 Продлить",
    CallbackAction.INSTRUCTION: "📖 Инструкция",
    CallbackAction.FRIENDS: "👫 Друзья",
    CallbackAction.NEW_SUB: "🚀 Подключить VPN",
    CallbackAction.START: "🏠 Главное меню",
    CallbackAction.YES: "✅ Оплатить",
    CallbackAction.NO: "❌ Отмена",
    CallbackAction.CANCEL: "❌ Отмена",
    CallbackAction.PAYMENT_SUCCESS: "✅ Я оплатил",
}

LEXICON_INLINE_DEVICE_RU: dict[str, str] = {
    DeviceType.ANDROID_PHONE: "📱 Android",
    DeviceType.IOS: "🍏 iPhone / iPad",
    DeviceType.TV_ANDROID: "📺 Android TV",
    DeviceType.COMPUTER_WINDOWS: "💻 Windows",
    DeviceType.COMPUTER_MACOS: "💻 MacOS",
}
```

#### 3.2: Обновить user_actions.py

- [ ] **Step 2: Обновить CallbackAction**

В `src/common/bot/keyboards/user_actions.py` заменить `CallbackAction`:

```python
class CallbackAction(StrEnum):
    # Навигация
    START = "start"
    MY_SUBSCRIPTION = "my_subscription"
    INSTRUCTION = "instruction"
    FRIENDS = "friends"

    # Подтверждение
    YES = "yes"
    NO = "no"

    # Оплата
    PAYMENT_SUCCESS = "payment_success"
    CANCEL = "cancel"
    RENEW_SUB = "renew"
    NEW_SUB = "new"
```

Убрать из enum: `VPN_ERROR`, `LIST_DEVICES`, `SUPPORT_HELP`, `INVITE`, `DEVICE_ERROR`, все `SETTINGS_*`.

`DeviceType`, `VpnAction`, `ChoiceType`, `PaymentStatus`, `ActualTariff`, `TARIFF_MATRIX` — оставить без изменений.

#### 3.3: Переписать keyboards.py

- [ ] **Step 3: Новое главное меню**

В `src/common/bot/keyboards/keyboards.py` заменить `get_keyboard_start()` на:

```python
def get_keyboard_main_menu(has_subscription: bool) -> InlineKeyboardMarkup:
    """Главное меню — сетка 2×2 + 2×1. URL-кнопки для кабинета и поддержки."""
    if has_subscription:
        rows = [
            [
                InlineKeyboardButton(text="📋 Подписка", callback_data=CallbackAction.MY_SUBSCRIPTION),
                InlineKeyboardButton(text="🔄 Продлить", callback_data=VpnCallback(action=VpnAction.RENEW).pack()),
            ],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton(
                    text="🚀 Подключить VPN",
                    callback_data=VpnCallback(action=VpnAction.NEW).pack(),
                ),
            ],
        ]

    rows.append([
        InlineKeyboardButton(text="📖 Инструкция", callback_data=CallbackAction.INSTRUCTION),
        InlineKeyboardButton(text="👫 Друзья", callback_data=CallbackAction.FRIENDS),
    ])
    rows.append([
        InlineKeyboardButton(text="🌐 Кабинет", url=app_config.auth.site_url),
        InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{app_config.bot.admin_username}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)
```

Добавить импорт в начало файла:

```python
from src.common.bot.keyboards.user_actions import VpnAction
from src.infrastructure.config import app_config
```

- [ ] **Step 4: Экран подписки**

Добавить:

```python
def get_keyboard_subscription(is_expiring: bool = False) -> InlineKeyboardMarkup:
    """Кнопки на экране 'Моя подписка'."""
    if is_expiring:
        rows = [
            [InlineKeyboardButton(
                text="🔄 Продлить подписку",
                callback_data=VpnCallback(action=VpnAction.RENEW).pack(),
            )],
            [
                InlineKeyboardButton(text="📖 Инструкция", callback_data=CallbackAction.INSTRUCTION),
                InlineKeyboardButton(text="🏠 Меню", callback_data=CallbackAction.START),
            ],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton(
                    text="🔄 Продлить",
                    callback_data=VpnCallback(action=VpnAction.RENEW).pack(),
                ),
                InlineKeyboardButton(text="📖 Инструкция", callback_data=CallbackAction.INSTRUCTION),
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackAction.START)],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
```

- [ ] **Step 5: Экран выбора количества устройств — с бейджем «хит»**

Заменить `get_keyboard_device_count()`:

```python
def get_keyboard_device_count(
    action: str, referral_id: int | None = None
) -> InlineKeyboardMarkup:
    """Шаг 1: выбор количества устройств. 3 устройства выделены как хит."""
    labels = {1: "📱 1 устройство", 2: "📱📱 2 устройства", 3: "⭐ 📱📱📱 3 устройства — хит"}
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for count in (1, 2, 3):
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=labels[count],
                callback_data=VpnCallback(
                    action=action,
                    device_limit=count,
                    duration=0,
                    referral_id=referral_id,
                ).pack(),
            )
        ])
    return keyboard
```

**Важно:** убран параметр `device` — он больше не нужен (happ для всех платформ).

- [ ] **Step 6: Экран выбора тарифа — с бейджами «хит» и «выгодно»**

Заменить `get_keyboard_tariff()`:

```python
def get_keyboard_tariff(
    action: str,
    device_limit: int = 1,
    referral_id: int | None = None,
) -> InlineKeyboardMarkup:
    """Шаг 2: выбор тарифа. 3 мес = хит, 6 мес = выгодно."""
    prices = TARIFF_MATRIX[device_limit]
    month_price = prices[1]

    badges = {3: " ⭐ хит", 6: " 💰 выгодно"}
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for months, label in [(1, "1 мес"), (3, "3 мес"), (6, "6 мес"), (12, "12 мес")]:
        price = prices[months]
        discount = round((1 - price / (month_price * months)) * 100)
        discount_text = f" (-{discount}%)" if discount > 0 else ""
        badge = badges.get(months, "")
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{label} — {price}₽{discount_text}{badge}",
                callback_data=VpnCallback(
                    action=action,
                    device_limit=device_limit,
                    duration=months,
                    referral_id=referral_id,
                    payment=price,
                ).pack(),
            )
        ])
    return keyboard
```

**Важно:** убран параметр `device` — больше не нужен.

- [ ] **Step 7: Экран подтверждения — сетка «Оплатить / Отмена»**

Заменить `get_keyboard_yes_or_no_for_update()`:

```python
def get_keyboard_confirm_payment(
    action: str,
    device_limit: int,
    duration: int,
    payment: int,
    balance: int,
    referral_id: int | None = None,
) -> InlineKeyboardMarkup:
    """Шаг 3: подтверждение оплаты."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Оплатить",
                callback_data=VpnCallback(
                    action=action,
                    device_limit=device_limit,
                    duration=duration,
                    referral_id=referral_id,
                    payment=payment,
                    balance=balance,
                    choice=ChoiceType.YES,
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=VpnCallback(
                    action=action,
                    device_limit=device_limit,
                    duration=duration,
                    referral_id=referral_id,
                    payment=payment,
                    balance=balance,
                    choice=ChoiceType.NO,
                ).pack(),
            ),
        ]
    ])
```

- [ ] **Step 8: Экран инструкций — выбор платформы**

Добавить:

```python
def get_keyboard_instruction_platforms() -> InlineKeyboardMarkup:
    """Выбор платформы для инструкции."""
    platforms = [
        ("📱 Android", "android_phone"),
        ("🍏 iPhone / iPad", "ios"),
        ("💻 Windows", "windows"),
        ("💻 MacOS", "macos"),
        ("📺 Android TV", "tv"),
    ]
    rows = [
        [InlineKeyboardButton(text=label, callback_data=SettingsCallback(platform=code).pack())]
        for label, code in platforms
    ]
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackAction.START)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_keyboard_instruction_detail() -> InlineKeyboardMarkup:
    """Кнопки после инструкции — ключ, назад, меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мой ключ подписки", callback_data=CallbackAction.MY_SUBSCRIPTION)],
        [InlineKeyboardButton(text="◀️ Выбор платформы", callback_data=CallbackAction.INSTRUCTION)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackAction.START)],
    ])
```

- [ ] **Step 9: Экран друзей**

Добавить:

```python
def get_keyboard_friends(referral_code: str) -> InlineKeyboardMarkup:
    """Кнопки реферального экрана."""
    bot_name = app_config.bot.bot_name
    share_text = f"Попробуй VPN — 7 дней бесплатно! https://t.me/{bot_name}?start={referral_code}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться в Telegram", switch_inline_query=share_text)],
        [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data=f"copy_ref:{referral_code}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackAction.START)],
    ])
```

- [ ] **Step 10: Проверить импорты**

```bash
uv run python -c "from src.common.bot.keyboards.keyboards import get_keyboard_main_menu, get_keyboard_subscription, get_keyboard_friends, get_keyboard_instruction_platforms; print('OK')"
```

- [ ] **Step 11: Commit**

```bash
git add src/common/bot/keyboards/keyboards.py src/common/bot/keyboards/user_actions.py src/common/bot/lexicon/lexicon.py
git commit -m "feat: new keyboard layouts — main menu grid, subscription, friends, instructions"
```

---

### Task 4: Text manager — новые тексты

**Files:**
- Modify: `src/common/bot/lexicon/text_manager.py`

- [ ] **Step 1: Добавить новые методы для главного меню**

В `src/common/bot/lexicon/text_manager.py` добавить:

```python
@staticmethod
def get_main_menu_active(user_name: str, end_date: str, used: int, limit: int, balance: int) -> str:
    return (
        f"👋 Привет, {user_name}!\n\n"
        f"✅ Подписка активна до {end_date}\n"
        f"📱 Устройств: {used} / {limit}\n"
        f"💰 Баланс: {balance}₽"
    )

@staticmethod
def get_main_menu_new(user_name: str) -> str:
    return (
        f"👋 Привет, {user_name}!\n\n"
        f"У вас пока нет активной подписки.\n"
        f"Подключите VPN и защитите свои данные! 🚀"
    )
```

- [ ] **Step 2: Добавить метод экрана подписки**

```python
@staticmethod
def get_subscription_info(
    end_date: str, device_limit: int, last_payment: int | None, subscription_url: str | None,
    days_left: int | None = None,
) -> str:
    text = "🔐 <b>Ваша подписка</b>\n\n"

    if days_left is not None and days_left <= 7:
        text += f"📅 Активна до: <b>{end_date}</b> ({days_left} дн.!)\n"
        text += "⚠️ <b>Продлите подписку, чтобы VPN не отключился</b>\n\n"
    else:
        text += f"📅 Активна до: <b>{end_date}</b>\n"

    text += f"📱 Устройств: <b>{device_limit}</b>\n"
    if last_payment is not None:
        text += f"💳 Последний платёж: <b>{last_payment}₽</b>\n"

    if subscription_url:
        text += f"\n🔗 <b>Ваш ключ для happ:</b>\n<code>{subscription_url}</code>"

    return text

@staticmethod
def get_no_subscription() -> str:
    return "У вас пока нет активной подписки."
```

- [ ] **Step 3: Добавить тексты для покупки (3 шага)**

```python
@staticmethod
def get_choose_device_count() -> str:
    return (
        "📱 <b>Сколько устройств подключить?</b>\n\n"
        "Одна подписка — на все ваши устройства: телефон, компьютер, телевизор."
    )

@staticmethod
def get_choose_tariff(device_limit: int) -> str:
    device_emoji = "📱" * device_limit
    device_word = {1: "устройство", 2: "устройства", 3: "устройства"}
    return (
        f"⏳ <b>Выберите срок подписки</b>\n\n"
        f"{device_emoji} {device_limit} {device_word[device_limit]}"
    )

@staticmethod
def get_confirm_payment(
    device_limit: int, duration: int, price: int, bonus: int, total: int,
) -> str:
    month_word = {1: "1 месяц", 3: "3 месяца", 6: "6 месяцев", 12: "12 месяцев"}
    text = (
        f"🔐 <b>Подтвердите подписку</b>\n\n"
        f"📱 Устройств: <b>{device_limit}</b>\n"
        f"⏳ Срок: <b>{month_word.get(duration, f'{duration} мес')}</b>\n"
        f"💰 Стоимость: <b>{price}₽</b>\n"
    )
    if bonus > 0:
        text += f"🎁 Бонус: <b>-{bonus}₽</b>\n"
    text += f"\n💳 К оплате: <b>{total}₽</b>"
    return text
```

- [ ] **Step 4: Добавить тексты для реферального экрана**

```python
@staticmethod
def get_friends_screen(invited_count: int, total_earned: int, balance: int) -> str:
    return (
        f"👫 <b>Пригласи друга</b>\n\n"
        f"Ты получаешь <b>50₽</b>, друг — <b>7 дней VPN бесплатно</b>\n\n"
        f"📊 <b>Твоя статистика:</b>\n"
        f"Приглашено: <b>{invited_count}</b>\n"
        f"Заработано: <b>{total_earned}₽</b>\n"
        f"💰 Баланс: <b>{balance}₽</b>"
    )
```

- [ ] **Step 5: Обновить инструкции — happ вместо v2RayTun**

Заменить методы `get_android_settings()`, `get_settings_iphone()`, `get_computer_settings()`:

```python
@staticmethod
def get_instruction(platform: str) -> str:
    instructions = {
        "android_phone": (
            "📱 <b>Подключение на Android</b>\n\n"
            "1️⃣ Скачайте <b>happ</b>:\n"
            '<a href="https://play.google.com/store/apps/details?id=app.hiddify.com">→ Google Play</a>\n\n'
            "2️⃣ Откройте приложение\n\n"
            "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
            "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
            "✅ <b>Готово!</b> VPN активен."
        ),
        "ios": (
            "🍏 <b>Подключение на iPhone / iPad</b>\n\n"
            "1️⃣ Скачайте <b>happ</b>:\n"
            '<a href="https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532">→ App Store</a>\n\n'
            "2️⃣ Откройте приложение\n\n"
            "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
            "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
            "✅ <b>Готово!</b> VPN активен."
        ),
        "windows": (
            "💻 <b>Подключение на Windows</b>\n\n"
            "1️⃣ Скачайте <b>happ</b>:\n"
            '<a href="https://apps.microsoft.com/detail/9pdfnl3qv2s5">→ Microsoft Store</a>\n\n'
            "2️⃣ Установите и откройте приложение\n\n"
            "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
            "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
            "✅ <b>Готово!</b> VPN активен."
        ),
        "macos": (
            "💻 <b>Подключение на MacOS</b>\n\n"
            "1️⃣ Скачайте <b>happ</b>:\n"
            '<a href="https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532">→ App Store</a>\n\n'
            "2️⃣ Установите и откройте приложение\n\n"
            "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
            "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
            "✅ <b>Готово!</b> VPN активен."
        ),
        "tv": (
            "📺 <b>Подключение на Android TV</b>\n\n"
            "1️⃣ Скачайте <b>happ</b> из Google Play на ТВ\n\n"
            "2️⃣ Откройте приложение\n\n"
            "3️⃣ Добавьте ваш ключ подписки\n\n"
            "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
            "✅ <b>Готово!</b> VPN активен."
        ),
    }
    return instructions.get(platform, "Платформа не найдена")
```

- [ ] **Step 6: Проверить**

```bash
uv run python -c "from src.common.bot.lexicon.text_manager import bot_repl; print(bot_repl.get_main_menu_active('Тест', '15.05.2026', 2, 3, 50))"
```

- [ ] **Step 7: Commit**

```bash
git add src/common/bot/lexicon/text_manager.py
git commit -m "feat: new text manager — subscription model, happ instructions, friends stats"
```

---

### Task 5: User router — /start, /invite, друзья, подписка, инструкция

**Files:**
- Modify: `src/apps/user/controllers/bot/router.py`
- Modify: `src/common/bot/router.py`

- [ ] **Step 1: Переписать handle_start (пользователь с подпиской)**

В `src/apps/user/controllers/bot/router.py` переписать `handle_start`:

```python
from src.apps.device.application.interfaces.view import DeviceView

@router.message(Command(CallbackAction.START))
async def handle_start(
    msg: types.Message,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
    device_view: FromDishka[DeviceView],
) -> None:
    referral_code = msg.text.split(" ")[1] if len(msg.text.split(" ")) > 1 else None

    if referral_code:
        try:
            user = await interactor.get_or_create(
                GetOrCreateUser(telegram_id=msg.from_user.id, referred_by_code=referral_code)
            )
        except ReferralNotFound:
            await msg.answer(bot_repl.get_message_error_referral(), reply_markup=return_start())
            return

        if user.free_months:
            await msg.answer(
                "❌ Вы уже использовали бесплатный период ранее",
                reply_markup=return_start(),
            )
            return

        from src.apps.user.application.interfaces.gateway import UserGateway  # noqa: PLC0415
        gateway: UserGateway = interactor._gateway  # type: ignore[attr-defined]
        referrer = await gateway.get_by_referral_code(referral_code)
        referral_id = referrer.telegram_id if referrer else None

        # Реферальный flow — сразу к выбору количества устройств
        await msg.answer(
            bot_repl.get_start_message_free_month(msg.from_user.full_name),
            reply_markup=get_keyboard_device_count(action=VpnAction.REFERRAL, referral_id=referral_id),
        )
        return

    user = await interactor.get_or_create(GetOrCreateUser(telegram_id=msg.from_user.id))
    sub = await device_view.get_subscription_info(msg.from_user.id)

    if sub and sub.end_date:
        end_str = sub.end_date.strftime("%d.%m.%Y")
        await msg.answer(
            bot_repl.get_main_menu_active(
                msg.from_user.full_name, end_str, sub.device_limit, sub.device_limit, user.balance
            ),
            reply_markup=get_keyboard_main_menu(has_subscription=True),
        )
    else:
        await msg.answer(
            bot_repl.get_main_menu_new(msg.from_user.full_name),
            reply_markup=get_keyboard_main_menu(has_subscription=False),
        )
```

Обновить импорты в начале файла:

```python
from src.apps.device.application.interfaces.view import DeviceView
from src.common.bot.keyboards.keyboards import (
    get_keyboard_device_count,
    get_keyboard_friends,
    get_keyboard_instruction_detail,
    get_keyboard_instruction_platforms,
    get_keyboard_main_menu,
    get_keyboard_subscription,
    return_start,
)
from src.common.bot.keyboards.user_actions import CallbackAction, VpnAction
```

- [ ] **Step 2: Переписать handle_start_callback**

```python
@router.callback_query(F.data.in_([CallbackAction.CANCEL, CallbackAction.START]))
async def handle_start_callback(
    call: types.CallbackQuery,
    interactor: FromDishka[UserInteractor],
    device_view: FromDishka[DeviceView],
) -> None:
    try:
        user = await interactor.get_or_create(GetOrCreateUser(telegram_id=call.from_user.id))
        sub = await device_view.get_subscription_info(call.from_user.id)

        if sub and sub.end_date:
            end_str = sub.end_date.strftime("%d.%m.%Y")
            await call.message.answer(
                bot_repl.get_main_menu_active(
                    call.from_user.full_name, end_str, sub.device_limit, sub.device_limit, user.balance
                ),
                reply_markup=get_keyboard_main_menu(has_subscription=True),
            )
        else:
            await call.message.answer(
                bot_repl.get_main_menu_new(call.from_user.full_name),
                reply_markup=get_keyboard_main_menu(has_subscription=False),
            )
    except Exception:
        log.exception("handle_start_callback_error")
        await call.message.answer(
            "Что-то пошло не так. Попробуйте позже или напишите в поддержку.",
        )
```

- [ ] **Step 3: Добавить обработчик «📋 Подписка»**

```python
@router.callback_query(F.data == CallbackAction.MY_SUBSCRIPTION)
async def handle_my_subscription(
    call: types.CallbackQuery,
    device_view: FromDishka[DeviceView],
) -> None:
    sub = await device_view.get_subscription_info(call.from_user.id)
    if sub is None or sub.end_date is None:
        await call.message.answer(
            bot_repl.get_no_subscription(),
            reply_markup=get_keyboard_main_menu(has_subscription=False),
        )
        await call.answer()
        return

    from datetime import datetime, UTC
    days_left = (sub.end_date - datetime.now(UTC)).days
    end_str = sub.end_date.strftime("%d.%m.%Y")

    await call.message.answer(
        bot_repl.get_subscription_info(
            end_date=end_str,
            device_limit=sub.device_limit,
            last_payment=sub.last_payment_amount,
            subscription_url=sub.subscription_url,
            days_left=days_left,
        ),
        reply_markup=get_keyboard_subscription(is_expiring=days_left <= 7),
    )
    await call.answer()
```

- [ ] **Step 4: Добавить обработчик «📖 Инструкция» (выбор платформы)**

```python
@router.callback_query(F.data == CallbackAction.INSTRUCTION)
async def handle_instruction(call: types.CallbackQuery) -> None:
    await call.message.answer(
        "📖 <b>Инструкция по подключению</b>\n\nВыберите вашу платформу:",
        reply_markup=get_keyboard_instruction_platforms(),
    )
    await call.answer()
```

- [ ] **Step 5: Добавить обработчик «👫 Друзья»**

```python
@router.callback_query(F.data == CallbackAction.FRIENDS)
async def handle_friends(
    call: types.CallbackQuery,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
) -> None:
    result = await interactor.get_referral_code(GetReferralCode(telegram_id=call.from_user.id))
    stats = await user_view.get_referral_stats(call.from_user.id)
    await call.message.answer(
        bot_repl.get_friends_screen(stats.invited_count, stats.total_earned, stats.balance),
        reply_markup=get_keyboard_friends(result.referral_code),
    )
    await call.answer()
```

- [ ] **Step 6: Добавить обработчик «📋 Скопировать ссылку»**

```python
@router.callback_query(F.data.startswith("copy_ref:"))
async def handle_copy_ref(call: types.CallbackQuery) -> None:
    referral_code = call.data.split(":", 1)[1]
    bot_name = app_config.bot.bot_name
    link = f"https://t.me/{bot_name}?start={referral_code}"
    await call.message.answer(f"🔗 Ваша реферальная ссылка:\n\n<code>{link}</code>")
    await call.answer()
```

- [ ] **Step 7: Обновить handle_invite (команда /invite)**

```python
@router.message(Command("invite"))
async def handle_invite(
    msg: types.Message,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
) -> None:
    result = await interactor.get_referral_code(GetReferralCode(telegram_id=msg.from_user.id))
    stats = await user_view.get_referral_stats(msg.from_user.id)
    await msg.answer(
        bot_repl.get_friends_screen(stats.invited_count, stats.total_earned, stats.balance),
        reply_markup=get_keyboard_friends(result.referral_code),
    )
```

- [ ] **Step 8: Проверить**

```bash
uv run python -c "from src.apps.user.controllers.bot.router import router; print('OK')"
```

- [ ] **Step 9: Commit**

```bash
git add src/apps/user/controllers/bot/router.py
git commit -m "feat: new user router — main menu grid, subscription screen, friends with stats"
```

---

### Task 6: Common router — инструкции для happ

**Files:**
- Modify: `src/common/bot/router.py`

- [ ] **Step 1: Переписать обработчики инструкций**

Заменить содержимое `src/common/bot/router.py`:

```python
import structlog
from aiogram import F, Router, types
from aiogram.filters import Command
from dishka.integrations.aiogram import FromDishka

from src.common.bot.cbdata import SettingsCallback
from src.common.bot.keyboards.keyboards import (
    get_keyboard_instruction_detail,
    get_keyboard_instruction_platforms,
)
from src.common.bot.keyboards.user_actions import CallbackAction
from src.common.bot.lexicon.text_manager import bot_repl

log = structlog.get_logger(__name__)
router = Router()


@router.message(Command("help"))
async def handle_help_command(msg: types.Message) -> None:
    await msg.answer(
        "📖 <b>Инструкция по подключению</b>\n\nВыберите вашу платформу:",
        reply_markup=get_keyboard_instruction_platforms(),
    )


@router.callback_query(SettingsCallback.filter())
async def handle_settings(call: types.CallbackQuery, callback_data: SettingsCallback) -> None:
    text = bot_repl.get_instruction(callback_data.platform)
    await call.message.answer(
        text,
        reply_markup=get_keyboard_instruction_detail(),
        disable_web_page_preview=True,
    )
    await call.answer()
```

Убрано: `handle_vpn_error`, `handle_device_error_report`, `handle_help_callback`, все импорты `DeviceView`, `Bot`, `ADMIN_ID`.

- [ ] **Step 2: Проверить**

```bash
uv run python -c "from src.common.bot.router import router; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/common/bot/router.py
git commit -m "feat: common router — happ instructions, removed vpn_error handlers"
```

---

### Task 7: Device router — упрощённый флоу покупки

**Files:**
- Modify: `src/apps/device/controllers/bot/router.py`

Ключевые изменения:
- Убрать шаг «тип устройства» (шаг 1 → сразу шаг 1.5)
- В `VpnCallback` поле `device` больше не используется для выбора типа — передаём `"vpn"` как заглушку
- Шаг 3 (подтверждение) использует новую клавиатуру и текст
- Шаги 6a/6b остаются для ручного флоу, ЮKassa уже работает

- [ ] **Step 1: Обновить импорты**

В `src/apps/device/controllers/bot/router.py` заменить импорты клавиатур:

```python
from src.common.bot.keyboards.keyboards import (
    get_keyboard_admin_confirm,
    get_keyboard_approve_payment_or_cancel,
    get_keyboard_confirm_payment,
    get_keyboard_device_count,
    get_keyboard_main_menu,
    get_keyboard_payment_link,
    get_keyboard_skip_email,
    get_keyboard_tariff,
    get_keyboard_vpn_received,
    return_start,
)
```

Убрать из импортов: `create_inline_kb`, `get_keyboard_devices`, `get_keyboard_devices_for_del`, `get_keyboard_for_details_device`, `get_keyboard_type_device`, `get_keyboard_yes_or_no_for_update`.

- [ ] **Step 2: Переписать handle_vpn_flow**

Основные изменения в шагах VpnCallback:

```python
@router.callback_query(VpnCallback.filter())
async def handle_vpn_flow(
    call: types.CallbackQuery,
    callback_data: VpnCallback,
    bot: Bot,
    state: FSMContext,
    interactor: FromDishka[DeviceInteractor],
    user_interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
) -> None:
    action = callback_data.action
    device_limit = callback_data.device_limit
    duration = callback_data.duration
    referral_id = callback_data.referral_id
    payment = callback_data.payment
    balance = callback_data.balance
    choice = callback_data.choice
    payment_status = callback_data.payment_status

    # Шаг 1: выбор количества устройств
    if device_limit is None:
        await call.message.edit_text(
            bot_repl.get_choose_device_count(),
            reply_markup=get_keyboard_device_count(action=action, referral_id=referral_id),
        )
        await call.answer()
        return

    # Шаг 2: выбор тарифа
    if duration == 0:
        await call.message.edit_text(
            bot_repl.get_choose_tariff(device_limit),
            reply_markup=get_keyboard_tariff(
                action=action, device_limit=device_limit, referral_id=referral_id
            ),
        )
        await call.answer()
        return

    # Шаг 3: показ суммы к оплате
    if balance is None:
        user_balance = await user_view.get_balance(call.from_user.id)
        finally_payment = max(payment - user_balance, 0)
        balance_to_deduct = min(user_balance, payment)
        bonus = payment - finally_payment
        await call.message.edit_text(
            bot_repl.get_confirm_payment(
                device_limit=device_limit,
                duration=duration,
                price=payment,
                bonus=bonus,
                total=finally_payment,
            ),
            reply_markup=get_keyboard_confirm_payment(
                action=action,
                device_limit=device_limit,
                duration=duration,
                balance=balance_to_deduct,
                payment=finally_payment,
                referral_id=referral_id,
            ),
        )
        await call.answer()
        return

    # Шаг 4: отмена
    if choice == ChoiceType.NO or payment_status == PaymentStatus.FAILED:
        await call.message.delete()
        await call.message.answer(
            text=bot_repl.send_messages_cancel_choice(),
            reply_markup=return_start(),
        )
        await call.answer()
        return

    # Шаг 5: подтверждение → email → оплата
    if choice == ChoiceType.YES:
        await call.message.delete()

        user_email = await user_view.get_email(call.from_user.id)
        if user_email is None:
            await state.set_data(
                {
                    "action": action,
                    "device_limit": device_limit,
                    "duration": duration,
                    "referral_id": referral_id,
                    "payment": payment,
                    "balance": balance,
                }
            )
            await state.set_state(EmailInput.waiting_for_email)
            await call.message.answer(
                "📧 Укажите вашу электронную почту — она понадобится "
                "для входа на сайт и получения чеков.",
                reply_markup=get_keyboard_skip_email(),
            )
            await call.answer()
            return

        if app_config.yookassa.enabled:
            await _show_payment_link(
                call, interactor,
                action=action,
                device="vpn",
                device_limit=device_limit,
                duration=duration,
                amount=payment,
                balance=balance,
                device_name=None,
                user_telegram_id=call.from_user.id,
            )
            await call.answer()
            return

        await _show_qr_payment(
            call, action, "vpn", device_limit, duration, referral_id, payment, balance,
        )
        await call.answer()
        return

    # Шаг 6a: новая подписка — ожидание подтверждения админа
    if action == CallbackAction.NEW_SUB and payment_status == PaymentStatus.SUCCESS:
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            await call.answer()
            return
        await call.answer()
        pending = await interactor.create_pending_payment(
            CreatePendingPayment(
                user_telegram_id=call.from_user.id,
                action="new",
                device_type="vpn",
                duration=duration,
                amount=payment,
                balance_to_deduct=balance,
                device_limit=device_limit or 1,
            )
        )
        await call.message.delete()
        await call.message.answer("⏳ Ожидайте подтверждения оплаты администратором")
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💳 Новый платёж!\n"
                f"👤 @{call.from_user.username} (id: {call.from_user.id})\n"
                f"📱 Устройств: {device_limit}\n"
                f"📅 Срок: {duration} мес → {payment}₽"
            ),
            reply_markup=get_keyboard_admin_confirm(pending.id),
        )
        log.info(
            "pending_payment_created",
            pending_id=pending.id,
            user_id=call.from_user.id,
            duration=duration,
            amount=payment,
        )
        return

    # Шаг 6b: продление
    if action == VpnAction.RENEW and payment_status == PaymentStatus.SUCCESS:
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            await call.answer()
            return
        await call.answer()
        pending = await interactor.create_pending_payment(
            CreatePendingPayment(
                user_telegram_id=call.from_user.id,
                action="renew",
                device_type="vpn",
                duration=duration,
                amount=payment,
                balance_to_deduct=balance,
                device_limit=device_limit or 1,
            )
        )
        await call.message.delete()
        await call.message.answer("⏳ Ожидайте подтверждения оплаты администратором")
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔄 Продление подписки!\n"
                f"👤 @{call.from_user.username} (id: {call.from_user.id})\n"
                f"📱 Устройств: {device_limit}\n"
                f"📅 Срок: {duration} мес → {payment}₽"
            ),
            reply_markup=get_keyboard_admin_confirm(pending.id),
        )
        log.info(
            "pending_renewal_created",
            pending_id=pending.id,
            user_id=call.from_user.id,
            duration=duration,
            amount=payment,
        )
        return

    # Шаг 6c: реферальный бесплатный период
    if action == VpnAction.REFERRAL:
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            await call.answer()
            return
        await call.answer()
        result_free = await interactor.create_device_free(
            CreateDeviceFree(
                telegram_id=call.from_user.id,
                device_type="vpn",
                period_days=app_config.payment.free_month,
            )
        )
        log.info(
            "device_created_free",
            device_name=result_free.device_name,
            referral_id=referral_id,
        )
        await user_interactor.mark_free_month_used(MarkFreeMonthUsed(telegram_id=call.from_user.id))
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🎁 Реферальная подписка!\n"
                f"👤 @{call.from_user.username} (id: {call.from_user.id})\n"
                f"🆔 Пригласил: {referral_id}"
            ),
        )
        await call.message.answer(
            bot_repl.get_message_success_free_month("VPN"),
            reply_markup=return_start(),
        )
        if referral_id:
            await user_interactor.add_referral_bonus(
                AddReferralBonus(referrer_telegram_id=referral_id, amount=50)
            )
            log.info("referral_bonus_added", referrer_id=referral_id, amount=50)
            await bot.send_message(
                chat_id=referral_id, text=bot_repl.get_message_new_user_referral()
            )
```

- [ ] **Step 3: Обновить email-хендлеры — убрать `device` из state**

В `_show_qr_from_state`, `handle_email_input`, `handle_skip_email` — убрать `data["device"]` и заменить на `"vpn"`:

```python
async def _show_qr_from_state(
    msg_or_call: types.Message | types.CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    await state.clear()

    message = msg_or_call.message if isinstance(msg_or_call, types.CallbackQuery) else msg_or_call

    file_data = await get_photo_for_pay()
    await message.answer_photo(
        photo=file_data,
        caption=bot_repl.get_approve_payment(amount=data["payment"], payment_link=LINK),
        reply_markup=get_keyboard_approve_payment_or_cancel(
            action=data["action"],
            device="vpn",
            device_limit=data.get("device_limit", 1),
            duration=data["duration"],
            referral_id=data.get("referral_id"),
            payment=data["payment"],
            balance=data["balance"],
            choice=ChoiceType.STOP,
        ),
    )
```

В `handle_email_input` — при вызове `_show_payment_link` передавать `device="vpn"`.

В `handle_skip_email` — аналогично `device="vpn"`.

- [ ] **Step 4: Убрать неиспользуемые хендлеры**

Удалить из `src/apps/device/controllers/bot/router.py`:
- `handle_devices_cmd` (команда `/devices`)
- `handle_list_devices` (callback `LIST_DEVICES`)
- `handle_delete_prompt` (callback `del`)
- `handle_delete_confirm` (callback `DeviceDeleteCallback`)
- `handle_device_detail` (callback `DeviceConfCallback`)

Убрать неиспользуемые импорты: `DeviceConfCallback`, `DeviceDeleteCallback`, `DeleteDevice`, `DeviceView`, и всё что осталось неиспользуемым.

- [ ] **Step 5: Проверить**

```bash
uv run python -c "from src.apps.device.controllers.bot.router import router; print('OK')"
uv run pytest tests/unit/ -q --tb=short 2>&1 | tail -10
```

- [ ] **Step 6: Commit**

```bash
git add src/apps/device/controllers/bot/router.py
git commit -m "feat: simplified purchase flow — 3 steps, no device type selection"
```

---

### Task 8: Cleanup — удалить неиспользуемый код

**Files:**
- Modify: `src/common/bot/cbdata.py` — можно оставить `DeviceConfCallback`, `DeviceDeleteCallback`, `DeviceErrorCallback` пока (для обратной совместимости), но `SettingsCallback` обязательно оставить
- Modify: `src/common/bot/keyboards/keyboards.py` — удалить неиспользуемые функции
- Modify: `src/common/bot/lexicon/text_manager.py` — удалить старые методы

- [ ] **Step 1: Удалить из keyboards.py неиспользуемые функции**

Удалить:
- `get_keyboard_start()` — заменена на `get_keyboard_main_menu()`
- `get_keyboard_type_device()` — шаг выбора типа убран
- `get_keyboard_type_comp()` — не нужна
- `get_keyboard_tariff_for_update()` — заменена на `get_keyboard_tariff()`
- `get_keyboard_yes_or_no()` — не используется
- `get_keyboard_yes_or_no_for_update()` — заменена на `get_keyboard_confirm_payment()`
- `get_keyboard_device_test()` — пустая заглушка
- `get_keyboard_devices()` — список устройств убран
- `get_keyboard_devices_for_error()` — VPN error убран
- `get_keyboard_devices_for_del()` — удаление убрано
- `get_basic_menu()` — не нужна
- `get_keyboard_for_details_device()` — экран устройства убран
- `get_keyboard_approve_payment_or_cancel_for_update()` — не нужна
- `get_keyboard_help()` — заменена на `get_keyboard_instruction_platforms()`

- [ ] **Step 2: Удалить из text_manager.py старые методы**

Удалить:
- `get_start_message()` — заменён на `get_main_menu_new()`
- `get_start()` — заменён на `get_main_menu_active()`
- `get_message_devices()` — список устройств убран
- `generate_device_info_message()` — экран устройства убран
- `get_approve_payment()` — оставить (используется в QR-флоу)
- `get_help_text()` — убран
- `get_android_settings()` — заменён на `get_instruction()`
- `get_computer_settings()` — заменён на `get_instruction()`
- `get_settings_iphone()` — заменён на `get_instruction()`
- `get_message_admin_error()` — VPN error убран
- `get_full_info_payment()` — заменён на `get_confirm_payment()`
- `send_messages_for_admin_update()` — не используется
- `send_message_admin_new_device()` — не используется
- `send_message_admin_new_user_referral()` — упрощён inline

Оставить: `get_approve_payment()`, `get_approve_payment_link()`, `get_message_invite_friend()`, `get_message_success_free_month()`, `get_message_success_payment()`, `get_message_success_payment_update()`, `send_messages_end_pay()`, `send_messages_cancel_choice()`, `get_message_new_user_referral()`, `get_message_error_referral()`, `get_start_message_free_month()`.

- [ ] **Step 3: Удалить из user_actions.py неиспользуемое**

Удалить `ActualTariff` enum — цены берутся из `TARIFF_MATRIX`.

- [ ] **Step 4: Проверить что всё импортируется**

```bash
uv run python -c "
from src.common.bot.keyboards.keyboards import get_keyboard_main_menu
from src.common.bot.lexicon.text_manager import bot_repl
from src.apps.user.controllers.bot.router import router as user_router
from src.apps.device.controllers.bot.router import router as device_router
from src.common.bot.router import router as common_router
print('ALL OK')
"
```

- [ ] **Step 5: Запустить тесты**

```bash
uv run pytest tests/unit/ -q --tb=short 2>&1 | tail -10
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove unused keyboards, texts, and device-based handlers"
```

---

### Task 9: Обновить регистрацию команд бота

**Files:**
- Modify: `main_bot.py`

- [ ] **Step 1: Обновить set_commands**

Найти в `main_bot.py` вызов `set_my_commands` и обновить список:

```python
await bot.set_my_commands([
    BotCommand(command="start", description="🏠 Главное меню"),
    BotCommand(command="invite", description="👫 Пригласить друга"),
    BotCommand(command="help", description="📖 Инструкция"),
])
```

Убрать команду `/devices` — больше не нужна.

- [ ] **Step 2: Проверить**

```bash
uv run python -c "from main_bot import *; print('OK')" 2>&1 | head -5
```

- [ ] **Step 3: Commit**

```bash
git add main_bot.py
git commit -m "feat: update bot commands — remove /devices, add descriptions"
```
