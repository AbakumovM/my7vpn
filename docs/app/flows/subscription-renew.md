# Продление подписки

**Точка входа:** кнопка "🔄 Продлить" → `VpnCallback(action=VpnAction.RENEW)`
**Файл:** `src/apps/device/controllers/bot/router.py` → `handle_vpn_flow()`

---

## Отличия от покупки новой подписки

Флоу **идентичен** флоу новой подписки (те же шаги 1–5), кроме:
- `action = VpnAction.RENEW` (вместо `VpnAction.NEW`)
- При `confirm_payment()` продлевается **существующая** подписка, а не создаётся новая

---

## Что происходит при confirm_payment (action="renew")

**Файл:** `src/apps/device/application/interactor.py` → `confirm_payment()`

1. Загрузить PendingPayment
2. Списать баланс с пользователя
3. Получить текущую подписку: `subscription_gateway.get_active_by_telegram_id(telegram_id)`
4. Продлить:
   - Если подписка активна (end_date > now): `end_date = current_end_date + months`
   - Иначе: `end_date = now + months`
5. Обновить Remnawave: `remnawave_gateway.update_user(uuid, expire_at=new_end_date, device_limit=X)`
6. Сохранить обновлённую `UserSubscription`
7. Создать `UserPayment`
8. Начислить бонус рефереру (если первая платная покупка — аналогично `new`)
9. Удалить PendingPayment

---

## Результат для пользователя (action="renew")
```
✅ Подписка продлена до DD.MM.YYYY.
```
Клавиатура: `get_keyboard_vpn_received()` (кнопки: Инструкция, Главное меню)

---

## Ключевые файлы
| Файл | Назначение |
|------|-----------|
| `src/apps/device/controllers/bot/router.py` | handle_vpn_flow (тот же handler что и для new) |
| `src/apps/device/application/interactor.py` | confirm_payment — ветка action="renew" |
| `src/apps/device/adapters/gateway.py` | SQLAlchemySubscriptionGateway.save() |
| `src/infrastructure/remnawave/client.py` | update_user |

> Подробнее про шаги 1–5 и варианты оплаты: [subscription-new.md](subscription-new.md)
