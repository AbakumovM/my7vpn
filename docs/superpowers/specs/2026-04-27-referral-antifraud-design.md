# Referral Program: Bug Fixes & Anti-Fraud Design

**Date:** 2026-04-27
**Status:** Approved

---

## Context

The referral program has several bugs and no anti-fraud protection:

1. With YooKassa enabled, the referral flow incorrectly creates a paid pending payment instead of a free subscription — the free activation path is never reached.
2. The referral flow shows a tariff/device selector (with prices) before giving a free subscription.
3. `CreateDeviceFree` ignores `device_limit`; free subscriptions create a legacy `Device/Subscription` pair instead of `UserSubscription`, making free users invisible to the notification scheduler and inconsistent with the paid flow.
4. No self-referral protection.
5. Existing users can navigate the referral flow and get a free month if `free_months=False`.
6. Referral bonus is credited on free activation — trivially abusable via fake Telegram accounts.

---

## Goals

- Fix the broken referral flow (YooKassa + free activation)
- Unify free and paid subscriptions under `UserSubscription`
- Add anti-fraud: self-referral prevention, new-users-only gate, deferred bonus
- Referral bonus credited only after referred user's first paid purchase
- Referrer notified when bonus is credited

---

## Section 1: Referral Flow

### New flow

```
/start {code}
  → validate (3 checks)
  → show welcome screen with single "Активировать" button
  → VpnAction.REFERRAL callback
  → create_device_free (1 device, N days from config)
  → mark_free_month_used
  → send subscription_url to user
```

### Validation in `handle_start`

Performed before showing any screen:

1. **Code exists:** `gateway.get_by_referral_code(code)` → if None: "Недействительная реферальная ссылка" + return_start()
2. **Not self-referral:** `referrer.telegram_id != msg.from_user.id` → if equal: raise `SelfReferralError` → "Нельзя использовать собственную реферальную ссылку" + return_start()
3. **User is new:** check `gateway.get_by_telegram_id(msg.from_user.id)` before `get_or_create` → if exists: "Вы уже зарегистрированы. Используйте /start для входа в меню." + return_start()

If all checks pass:
- Call `get_or_create` with `referred_by_code` to create the user with `referred_by` set
- Show welcome message (e.g. "🎁 Вам доступен бесплатный период!") with single button `VpnAction.REFERRAL`

### Changes in `handle_vpn_flow`

When `action == VpnAction.REFERRAL`: **skip steps 1–5** entirely. Jump directly to the activation logic (currently step 6c). `device_limit` is hardcoded to `1`, `duration` is taken from `app_config.payment.free_month`.

No tariff selection, no payment screens, no email prompt.

---

## Section 2: Data Model — Free Subscription via UserSubscription

### `CreateDeviceFree` command

Add `device_limit: int = 1` field (currently missing).

### `DeviceInteractor.create_device_free`

Replace legacy `Device + Subscription` creation with:

1. Check if user already has `remnawave_uuid`:
   - No → `remnawave_gateway.create_user(telegram_id, expire_at, device_limit=1)` → set `user.remnawave_uuid`, `user.subscription_url`
   - Yes → `remnawave_gateway.update_user(uuid, expire_at, device_limit=1)` → verify `subscription_url` exists
2. Create `UserSubscription(user_telegram_id, plan=period_days, start_date, end_date, device_limit=1, is_active=True)`
3. Create `UserPayment(user_telegram_id, subscription_id, amount=0, duration=period_days, device_limit=1)`
4. Save user, commit

### New return type: `FreeSubscriptionInfo`

```python
@dataclass(frozen=True)
class FreeSubscriptionInfo:
    user_telegram_id: int
    subscription_url: str
    end_date: datetime
```

Replaces `DeviceCreatedInfo` for the free flow. Controller sends `subscription_url` to the user.

---

## Section 3: Deferred Referral Bonus

### Where

`DeviceInteractor.confirm_payment` — called by both YooKassa webhook and admin manual confirmation.

### Logic

Before saving the new `UserPayment`:

```python
existing_count = await self._subscription_gateway.count_payments_for_user(user.telegram_id)
referrer_telegram_id: int | None = None
if existing_count == 0 and user.referred_by is not None:
    referrer = await self._user_gateway.get_by_telegram_id(user.referred_by)
    if referrer is not None:
        referrer.balance += 50
        await self._user_gateway.save(referrer)
        referrer_telegram_id = referrer.telegram_id
```

### `ConfirmPaymentResult` update

Add field:
```python
referrer_telegram_id: int | None = None
```

### Controllers

Both `handle_admin_confirm` (bot router) and `yookassa_webhook` (HTTP router):

```python
if result.referrer_telegram_id is not None:
    try:
        await bot.send_message(
            chat_id=result.referrer_telegram_id,
            text="🎉 Ваш друг оформил подписку! Вам начислено 50 руб. на баланс.",
        )
    except Exception:
        log.warning("referral_bonus_notify_failed", referrer_id=result.referrer_telegram_id)
```

### Removed from current code

- `add_referral_bonus` call in `handle_vpn_flow` step 6c (REFERRAL handler)
- Referrer notification (`bot.send_message` to referrer) in step 6c

### `SubscriptionGateway` protocol — new method

```python
async def count_payments_for_user(self, telegram_id: int) -> int: ...
```

Implementation: `SELECT COUNT(*) FROM user_payments WHERE user_telegram_id = :telegram_id`

---

## Section 4: Edge Cases & Error Handling

### New exceptions

- `SelfReferralError(telegram_id: int)` in `src/apps/user/domain/exceptions.py`
  - Caught in `handle_start`, shown as user-facing message

### `create_device_free` — Remnawave failure

If Remnawave is unavailable, the exception propagates up. The DB transaction is not committed. The user sees a generic error message. No partial state is saved.

### `confirm_payment` — referrer missing

If `user.referred_by` points to a deleted user: `referrer` is `None` → skip bonus silently, `referrer_telegram_id=None`. Transaction proceeds normally.

### Referrer notification failure

Caught in the controller. Logged as warning. Does **not** roll back the transaction — the bonus balance is already committed. The referrer simply doesn't receive the message (can be retried manually if needed).

### `count_payments_for_user` — ordering

The count query runs **before** `save_payment` for the current transaction. This guarantees `count == 0` exclusively for the first payment. No race condition possible within a single async request.

---

## Files Changed

| File | Change |
|------|--------|
| `src/apps/user/domain/exceptions.py` | Add `SelfReferralError` |
| `src/apps/user/domain/commands.py` | No changes needed |
| `src/apps/device/domain/commands.py` | Add `device_limit` to `CreateDeviceFree` |
| `src/apps/device/application/interactor.py` | `create_device_free` → UserSubscription + Remnawave; `confirm_payment` → deferred bonus; `ConfirmPaymentResult` → add `referrer_telegram_id` |
| `src/apps/device/application/interfaces/subscription_gateway.py` | Add `count_payments_for_user` |
| `src/apps/device/adapters/subscription_gateway.py` | Implement `count_payments_for_user` |
| `src/apps/user/controllers/bot/router.py` | `handle_start` → validation guards; remove `interactor._gateway` access |
| `src/apps/device/controllers/bot/router.py` | `handle_vpn_flow` → skip steps 1–5 for REFERRAL; remove bonus call; add referrer notify in `handle_admin_confirm` |
| `src/apps/device/controllers/http/yookassa_router.py` | Add referrer notify after `confirm_payment` |
