# HWID-устройства

HWID (Hardware ID) — механизм Remnawave для ограничения числа одновременно подключённых устройств. Пользователь может видеть и удалять свои подключения.

---

## Просмотр устройств

**Триггер:** кнопка "📱 Мои устройства" → `F.data == CallbackAction.HWID_DEVICES`
**Файл:** `src/apps/user/controllers/bot/router.py` → `handle_hwid_devices()`

```python
remnawave_uuid = await user_view.get_remnawave_uuid(telegram_id)
devices = await remnawave_gateway.get_hwid_devices(remnawave_uuid)
# devices: list[HwidDevice] с полями: hwid, platform, os_version, device_model
```

Показывает список: `"Model (Platform)"` — каждое с кнопкой ❌ удалить.

---

## Удаление одного устройства

**Триггер:** `F.data.startswith("hwid_del:")`
**Файл:** `src/apps/user/controllers/bot/router.py` → `handle_hwid_delete_one()`

```python
hwid = call.data.split(":", 1)[1]
await remnawave_gateway.delete_hwid_device(remnawave_uuid, hwid)
```

После удаления — обновить и показать актуальный список.

---

## Удаление всех устройств

**Шаг 1 (подтверждение):** `F.data == CallbackAction.HWID_DELETE_ALL`
→ показать `get_keyboard_confirm_delete_all()` с кнопками "Да, удалить все" / "Отмена"

**Шаг 2 (выполнение):** `F.data == CallbackAction.HWID_DELETE_ALL_CONFIRM`
**Файл:** `src/apps/user/controllers/bot/router.py` → `handle_hwid_delete_all_confirm()`

```python
await remnawave_gateway.delete_all_hwid_devices(remnawave_uuid)
```

---

## Хелперы

```python
# Количество подключённых устройств (для главного меню)
async def _get_hwid_used(remnawave_uuid, remnawave_gateway) -> int
# При ошибке возвращает 0, не падает

# Список устройств как list[dict] для клавиатуры
async def _get_hwid_device_dicts(telegram_id, user_view, remnawave_gateway) -> list[dict] | None
# None если нет remnawave_uuid
```

---

## Лимит устройств

Лимит устанавливается при создании/обновлении аккаунта в Remnawave:
- `hwidDeviceLimit` при `create_user()` / `update_user()`
- Берётся из `PendingPayment.device_limit` → `UserSubscription.device_limit`
- Отображается в главном меню: `"Подключено: {used}/{limit}"`

---

## Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `src/apps/user/controllers/bot/router.py` | handle_hwid_devices, handle_hwid_delete_one, handle_hwid_delete_all_confirm |
| `src/apps/device/adapters/remnawave_gateway.py` | get_hwid_devices, delete_hwid_device, delete_all_hwid_devices |
| `src/infrastructure/remnawave/client.py` | HTTP-клиент Remnawave |
| `src/common/bot/keyboards/keyboards.py` | get_keyboard_hwid_devices, get_keyboard_confirm_delete_all |
| `src/common/bot/lexicon/text_manager.py` | get_hwid_devices_screen, get_hwid_delete_all_confirm |
