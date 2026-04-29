# Реферальная система

---

## Как работает

1. Пользователь A получает реф-ссылку → делится
2. Новый пользователь B регистрируется по ссылке → получает бесплатный период
3. При **первом платном платеже** B → A получает 50₽ на баланс

---

## Получение реф-ссылки

**Команда:** `/invite` или кнопка "👫 Друзья"
**Файл:** `src/apps/user/controllers/bot/router.py` → `handle_friends()`, `handle_invite()`

```python
result = await interactor.get_referral_code(GetReferralCode(telegram_id))
# result.referral_code — MD5 хэш от telegram_id, первые 8 символов
link = f"https://t.me/{bot_name}?start={result.referral_code}"
```

**Статистика реферала:** `user_view.get_referral_stats(telegram_id)`
```python
ReferralStats:
    invited_count: int   # кол-во приглашённых
    total_earned: int    # invited_count * 50
    balance: int         # текущий баланс
```

---

## Регистрация по реф-ссылке

**Триггер:** `/start {referral_code}`
**Файл:** `src/apps/user/controllers/bot/router.py` → `handle_start()`

Проверки:
1. Код существует: `user_view.get_referrer_telegram_id(referral_code)`
2. Пользователь не использует свою ссылку: `referral_id != msg.from_user.id`
3. Только новые пользователи: `user_view.get_user_id(telegram_id) is None`

При успехе:
- Создать пользователя с `referred_by_code=referral_code`
- Показать кнопку "🎁 Активировать бесплатный период"

---

## Активация бесплатного периода

**Триггер:** `VpnCallback(action=VpnAction.REFERRAL, referral_id=X)`
**Файл:** `src/apps/device/controllers/bot/router.py` → `handle_vpn_flow()` (шаг REFERRAL)

```python
await interactor.create_device_free(CreateDeviceFree(
    telegram_id=telegram_id,
    device_type="vpn",
    period_days=app_config.payment.free_month,  # настраивается
    device_limit=1,
))
await interactor.mark_free_month_used(MarkFreeMonthUsed(telegram_id))
```

Что делает `create_device_free()`:
1. Создать Remnawave аккаунт: `remnawave_gateway.create_user(telegram_id, expire_at=now+days, device_limit=1)`
2. Сохранить `remnawave_uuid` и `subscription_url` в User
3. Создать `UserSubscription(plan=period_days, ...)`
4. Создать `UserPayment(amount=0, payment_method="реферал")`

Уведомить **рефереру:** сообщение в бот (telegram_id из callback)
Уведомить **админа:** `"🎁 Реферальная подписка! ..."`
Отправить пользователю `subscription_url`

---

## Начисление бонуса рефереру

**Место:** `src/apps/device/application/interactor.py` → `confirm_payment()` (в конце)

```python
count = await self._subscription_gateway.count_payments_for_user(telegram_id)
if count == 0 and result.referrer_telegram_id is not None:
    await self._user_interactor.add_referral_bonus(
        AddReferralBonus(referrer_telegram_id=result.referrer_telegram_id, amount=50)
    )
    # + отправить сообщение рефереру в бот
```

Условия срабатывания:
- Это **первый платный** платёж нового пользователя (`count == 0`)
- У пользователя есть `referred_by` (реферер существует)
- Срабатывает при любом платном методе (YooKassa, QR, баланс)
- **НЕ срабатывает** при бесплатном (реферальном) получении подписки

---

## Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `src/apps/user/controllers/bot/router.py` | handle_start (регистрация по ссылке), handle_friends, handle_invite |
| `src/apps/user/application/interactor.py` | get_referral_code, add_referral_bonus, mark_free_month_used |
| `src/apps/device/application/interactor.py` | create_device_free, confirm_payment (начисление бонуса) |
| `src/apps/user/adapters/gateway.py` | get_by_referral_code, get_referral_stats |

---

## Поля в UserORM (src/apps/user/adapters/orm.py)

| Поле | Тип | Описание |
|------|-----|---------|
| `referral_code` | String | MD5[:8] от telegram_id |
| `referred_by` | BigInteger | telegram_id реферера |
| `free_months` | Boolean | использован ли бесплатный период |
| `balance` | Integer | бонусный баланс (₽) |
