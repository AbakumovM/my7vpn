"""
Шаг 1: Генерация шаблона маппинга из 3x-ui.

Запуск на сервере:
    uv run python scripts/generate_xui_mapping.py

Создаёт файл scripts/xui_mapping.json — заполни telegram_id для каждого клиента,
затем запусти scripts/sync_xui_to_db.py для импорта в БД.

Поля в файле:
  xui_email    — email клиента в 3x-ui (он же будет device_name в БД)
  xui_uuid     — UUID клиента (заполняется автоматически)
  telegram_id  — Telegram ID пользователя (ЗАПОЛНИ ВРУЧНУЮ; 0 = пропустить)
  device_type  — тип устройства для отображения (заполни вручную если нужно)
  sub_end_date — дата окончания подписки в формате YYYY-MM-DD (заполни вручную)
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, ".")

from src.infrastructure.config import app_config


async def main() -> None:
    xui = app_config.xui
    output = Path("scripts/xui_mapping.json")

    print("Подключаюсь к 3x-ui...")
    async with httpx.AsyncClient(base_url=xui.url, timeout=15.0) as http:
        login = await http.post(
            "/login",
            data={"username": xui.username, "password": xui.password},
        )
        login.raise_for_status()

        resp = await http.get("/panel/api/inbounds/list")
        resp.raise_for_status()
        data = resp.json()

    if not data.get("success"):
        raise RuntimeError(f"3x-ui inbounds/list failed: {data}")

    entries = []
    for inbound in data.get("obj", []):
        if inbound["id"] != xui.inbound_id:
            continue
        raw_settings = inbound.get("settings", "{}")
        settings = json.loads(raw_settings) if isinstance(raw_settings, str) else raw_settings
        for client in settings.get("clients", []):
            email = client.get("email", "")
            if not email:
                continue
            entries.append({
                "xui_email": email,
                "xui_uuid": client["id"],
                "telegram_id": 0,        # ← заполни
                "device_type": "",       # ← заполни: Android / iOS / Windows / MacOS / TV
                "sub_end_date": "",      # ← заполни: YYYY-MM-DD (дата окончания подписки)
            })

    entries.sort(key=lambda x: x["xui_email"])
    output.write_text(json.dumps(entries, ensure_ascii=False, indent=2))

    print(f"Готово. Найдено клиентов: {len(entries)}")
    print(f"Файл сохранён: {output}")
    print("\nЗаполни telegram_id (и опционально device_type, sub_end_date) для каждого клиента.")
    print("Клиентов с telegram_id=0 скрипт синхронизации пропустит.")


if __name__ == "__main__":
    asyncio.run(main())
