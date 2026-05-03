# Bug Fixes: Referral, Subscription Display, Payment — Design Spec

**Date:** 2026-05-03
**Branch:** fix_bugs

---

## Overview

Six targeted bug fixes across the bot and payment system. No new features, no architectural changes.

---

## Fix 1 — Referrer notification on free period activation

**Problem:** When an invited user activates the referral free period, the referrer receives no notification. Only the admin is notified.

**File:** `src/apps/device/controllers/bot/router.py`, `VpnAction.REFERRAL` handler (~line 204)

**Change:** After the admin notification, add:
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

---

## Fix 2 — "Заработано" → "Ожидаемый бонус" with clarification

**Problem:** The friends screen shows `Заработано: N₽` which equals `invited_count * 50`. This is misleading — the 50₽ bonus is only credited when an invited user makes their first paid payment.

**File:** `src/common/bot/lexicon/text_manager.py`, `get_friends_screen()` (~line 152)

**Change:**
```python
# Before
f"Заработано: <b>{total_earned}₽</b>\n"

# After
f"🎁 Ожидаемый бонус: <b>{total_earned}₽</b> (придёт на баланс когда друг оплатит подписку)\n"
```

---

## Fix 3 — Hardcoded "5 дней" → from config

**Problem:** Two places in `text_manager.py` hardcode "5 дней бесплатно" instead of reading from `app_config.payment.free_month`.

**Files:** `src/common/bot/lexicon/text_manager.py`

**Affected methods:**
- `get_main_menu_active()` (~line 48): `➜ Друг получает <b>5 дней бесплатно</b>`
- `get_friends_screen()` (~line 149): `друг — <b>5 дней VPN бесплатно</b>`

**Change:** Add `free_days: int` parameter to both methods. Pass `app_config.payment.free_month` at call sites in `user/controllers/bot/router.py`.

---

## Fix 4 — Expired subscription shows negative days

**Problem:** `get_subscription_info()` view does not filter by `end_date > now`, so expired subscriptions (with `is_active=True`) are returned. The bot displays "осталось -348 дн." because `days_left <= 7` catches negative values.

**Decision:** Fix at the view layer (option B) — add `end_date > now` filter. When subscription is expired, view returns `None`, controller shows "нет подписки" screen with a buy button. `is_active` field is not changed.

**File:** `src/apps/device/adapters/view.py`, `get_subscription_info()`

**Change:** Add `.where(UserSubscriptionORM.end_date > now)` to both the new-model query and the legacy fallback query.

---

## Fix 5 — Admin YooKassa notification missing payment details

**Problem:** The YooKassa webhook admin notification lacks amount, duration (months), and device_limit. After manual payment confirmation, the message is replaced with `"✅ Выдано: vpn"` — details are lost.

**Files:**
- `src/apps/device/application/interactor.py` — `ConfirmPaymentResult`
- `src/apps/device/controllers/http/yookassa_router.py` — admin notification
- (manual confirm handler is removed in Fix 6, so no change needed there)

**Change:** Add `amount: int`, `duration: int`, `device_limit: int` to `ConfirmPaymentResult`. Populate from `pending` object in `confirm_payment()`. Update YooKassa admin notification:

```
✅ ЮKassa автоплатёж
👤 {telegram_id}
Новая подписка / Продление до {end_date}
📱 Устройств: {device_limit} | 📅 {duration} мес | 💳 {amount}₽
payment_id: {payment_id}
```

---

## Fix 6 — Remove manual payment (QR + admin confirm/reject)

**Problem:** With `YOOKASSA__ENABLED=true` in production, the manual QR payment flow is unreachable dead code. Removing it reduces confusion and maintenance burden.

**What is removed:**

| Location | What |
|----------|------|
| `device/controllers/bot/router.py` | `_show_qr_payment()`, шаги 6a и 6b, `handle_admin_confirm`, `handle_admin_reject`, `LINK` variable, `yookassa.enabled` branch in step 5 |
| `common/bot/cbdata.py` | `AdminConfirmCallback`, `payment_status` field from `VpnCallback` |
| `common/bot/keyboards/keyboards.py` | `get_keyboard_approve_payment_or_cancel`, `get_keyboard_admin_confirm` |
| `common/bot/keyboards/user_actions.py` | `PaymentStatus` enum, `ChoiceType.STOP` |
| `infrastructure/config.py` | `payment_qr: str`, `payment_url: str` from `PaymentSettings` |

**What is NOT removed:**
- `PendingPayment` model, gateway, ORM — used by YooKassa webhook
- `create_pending_payment`, `confirm_payment` interactor methods
- `_show_payment_link` — the YooKassa path
- Bonus payment flow (`payment == 0`, direct confirm without YooKassa)
- `ChoiceType.YES`, `ChoiceType.NO` — still used in confirmation step

---

## Affected Files Summary

| File | Fixes |
|------|-------|
| `device/controllers/bot/router.py` | 1, 6 |
| `device/adapters/view.py` | 4 |
| `device/application/interactor.py` | 5 |
| `device/controllers/http/yookassa_router.py` | 5 |
| `common/bot/lexicon/text_manager.py` | 2, 3 |
| `user/controllers/bot/router.py` | 3 (call sites) |
| `common/bot/cbdata.py` | 6 |
| `common/bot/keyboards/keyboards.py` | 6 |
| `common/bot/keyboards/user_actions.py` | 6 |
| `infrastructure/config.py` | 6 |
