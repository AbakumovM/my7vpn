# Деплой на сервер — что сделано

**Сервер:** vm-nano
**Домен:** app.zevsgate.com
**Дата:** 2026-04-29

---

## Инфраструктура на сервере

- **nginx** — установлен нативно, терминирует SSL, проксирует на `127.0.0.1:8000`
- **certbot** — сертификат Let's Encrypt для `app.zevsgate.com`, автообновление настроено
- **Docker + Docker Compose** — три сервиса: `vpn-postgres`, `vpn-bot`, `vpn-web`
- **PostgreSQL** — запускается в Docker (образ `postgres:16-alpine`), данные в volume `vpn-bot_postgres_data`

## Открытые порты (ufw)

| Порт | Сервис |
|------|--------|
| 22   | SSH |
| 80   | nginx (HTTP → редирект на HTTPS) |
| 443  | nginx (HTTPS) |
| 5432 | PostgreSQL (открыт намеренно для экстренного доступа) |

## Расположение файлов

| Что | Где |
|-----|-----|
| Код и docker-compose | `/opt/vpn-bot/` |
| .env | `/opt/vpn-bot/.env` |
| nginx конфиг | `/etc/nginx/sites-available/vpn` |
| SSL сертификат | `/etc/letsencrypt/live/app.zevsgate.com/` |
| Дамп старой БД | `/tmp/vpn_backup_20260429_1805.sql` |

## Остановленные сервисы (старая инфраструктура)

```bash
sudo systemctl disable --now my_bot tech-bot ohrana x-ui
```

## Управление контейнерами

```bash
# Статус
docker compose -f docker-compose.prod.yml ps

# Логи
docker compose -f docker-compose.prod.yml logs bot --tail 50
docker compose -f docker-compose.prod.yml logs web --tail 50

# Перезапуск
docker compose -f docker-compose.prod.yml restart bot
docker compose -f docker-compose.prod.yml restart web

# Остановка всего
docker compose -f docker-compose.prod.yml down

# Обновление после git pull
git pull
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

## Мониторинг

```bash
# Статус всех контейнеров
docker compose -f docker-compose.prod.yml ps

# Следить за логами бота в реальном времени
docker compose -f docker-compose.prod.yml logs bot -f

# Следить за логами веба в реальном времени
docker compose -f docker-compose.prod.yml logs web -f

# Только ошибки
docker compose -f docker-compose.prod.yml logs bot --tail 100 | grep error

# Использование ресурсов контейнерами
docker stats

# Проверить что веб отвечает
curl -I https://app.zevsgate.com

# Проверить nginx
sudo systemctl status nginx
sudo nginx -t

# Место на диске
df -h

# Логи nginx (доступы и ошибки)
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## Миграции

```bash
docker compose -f docker-compose.prod.yml run --rm bot alembic upgrade head
```

## Особенности .env на сервере

- `DATABASE__URL` — указывает на `postgres` (имя Docker-сервиса), не `localhost`
- `AUTH__JWT_SECRET` — сгенерирован через `openssl rand -hex 32`
- `YOOKASSA__SECRET_KEY` — продовый ключ (`live_...`), не тестовый

## Перенос базы данных

Данные перелиты из нативного PostgreSQL (`mihailabakumov/vpn`) в Docker-контейнер:

```bash
sudo -u postgres pg_dump vpn > /tmp/vpn_backup.sql
cat /tmp/vpn_backup.sql | docker exec -i vpn-postgres psql -U "$PGUSER" -d vpn
docker compose -f docker-compose.prod.yml run --rm bot alembic upgrade head
```
