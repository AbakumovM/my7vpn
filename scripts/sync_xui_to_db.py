"""
Одноразовый скрипт: синхронизирует клиентов из 3x-ui с таблицей devices.

Для каждого устройства в БД без vpn_client_uuid ищет клиента в 3x-ui
по совпадению device_name == email, затем записывает uuid и vpn_config.

Запуск:
    uv run python scripts/sync_xui_to_db.py [--dry-run]

--dry-run: показывает что будет сделано, не трогает БД.
"""

import asyncio
import json
import sys

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, ".")

from src.infrastructure.config import app_config
from src.apps.device.adapters.orm import DeviceORM


async def fetch_xui_clients() -> list[dict]:
    """Получить всех клиентов из 3x-ui через REST API."""
    xui = app_config.xui
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

    clients = []
    for inbound in data.get("obj", []):
        if inbound["id"] != xui.inbound_id:
            continue
        raw_settings = inbound.get("settings", "{}")
        settings = json.loads(raw_settings) if isinstance(raw_settings, str) else raw_settings
        for client in settings.get("clients", []):
            clients.append({
                "uuid": client["id"],
                "email": client.get("email", ""),
            })
    return clients


async def run(dry_run: bool) -> None:
    xui = app_config.xui
    engine = create_async_engine(str(app_config.db.url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[call-overload]

    print("Получаю клиентов из 3x-ui...")
    clients = await fetch_xui_clients()
    print(f"Найдено клиентов в 3x-ui: {len(clients)}")

    client_map = {c["email"]: c["uuid"] for c in clients if c["email"]}

    async with async_session() as session:
        result = await session.execute(
            select(DeviceORM).where(DeviceORM.vpn_client_uuid.is_(None))
        )
        devices = result.scalars().all()
        print(f"Устройств в БД без uuid: {len(devices)}")

        updated = 0
        not_found = []

        for device in devices:
            uuid = client_map.get(device.device_name)
            if uuid is None:
                not_found.append(device.device_name)
                continue

            vless_link = xui.vless_template.format(uuid=uuid, name=device.device_name)
            print(f"  {'[DRY]' if dry_run else '[OK]'} {device.device_name} → uuid={uuid}")

            if not dry_run:
                await session.execute(
                    update(DeviceORM)
                    .where(DeviceORM.id == device.id)
                    .values(vpn_client_uuid=uuid, vpn_config=vless_link)
                )
            updated += 1

        if not dry_run:
            await session.commit()

    print(f"\nОбновлено: {updated}")
    if not_found:
        print(f"Не найдено в 3x-ui ({len(not_found)}):")
        for name in not_found:
            print(f"  - {name}")

    await engine.dispose()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN — БД не изменяется ===\n")
    asyncio.run(run(dry_run))
