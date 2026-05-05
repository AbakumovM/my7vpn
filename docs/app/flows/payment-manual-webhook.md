# Ручное доведение платежа YooKassa

Используется когда пользователь оплатил, но ключ не пришёл — сервер был выключен в момент оплаты и вебхук не отработал.

---

## Шаг 1 — получить pending_id из YooKassa

Выполнить локально (SHOP_ID и SECRET_KEY из `.env`):

```bash
curl -s -u SHOP_ID:SECRET_KEY \
  https://api.yookassa.ru/v3/payments/PAYMENT_ID | jq '.metadata, .status, .amount'
```

Убедиться что статус `succeeded`, из `metadata` взять `pending_id`.

---

## Шаг 2 — отправить вебхук на сервере

FastAPI слушает только на `127.0.0.1:8000` — выполнять **только с сервера** (через SSH):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/payments/yookassa/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event": "payment.succeeded",
    "object": {
      "id": "PAYMENT_ID",
      "status": "succeeded",
      "amount": {"value": "СУММА.00", "currency": "RUB"},
      "metadata": {"pending_id": "PENDING_ID"}
    }
  }'
```

Ожидаемый ответ: `{"status":"ok"}`

Если `{"status":"already_processed"}` — платёж уже был обработан ранее.

---

## Примечания

- Вебхук повторно проверяет статус через YooKassa API — фейковый платёж не пройдёт
- После успешной обработки пользователь получает ключ в боте автоматически
- Эндпоинт: `src/apps/device/controllers/http/yookassa_router.py`
