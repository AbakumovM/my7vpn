# Дизайн: Docker-развертывание

**Дата:** 2026-04-27
**Статус:** Утверждён

---

## Контекст

Бот работает как systemd-сервис на голом сервере с нативным Postgres. Dockerfile нет, reverse proxy нет, веб-сервис публично недоступен. YooKassa требует HTTPS для webhook-уведомлений — это не настроено.

Цель: перенести весь стек в Docker Compose с nginx + Let's Encrypt на хосте, сохранив существующую базу данных. Downtime при миграции — ~10 минут.

---

## Архитектура

**Подход:** Docker Compose для сервисов приложения (postgres, bot, web) + nginx нативно на хосте как reverse proxy с SSL-терминацией.

```
Интернет
   │
   ▼
nginx (хост, порты 80/443)
   │ proxy_pass 127.0.0.1:8000
   ▼
[контейнер web] uvicorn :8000
   │
   └──────────────────────────┐
                              ▼
[контейнер bot]  ──────► [контейнер postgres] :5432 (только внутренняя сеть)
```

---

## Секция 1: Docker-инфраструктура

### Файлы

| Файл | Назначение |
|------|-----------|
| `Dockerfile` | Единый образ для сервисов bot и web |
| `docker-compose.yml` | Локальная разработка: postgres + pgadmin (без изменений) |
| `docker-compose.prod.yml` | Production: postgres + bot + web |
| `.env.example` | Шаблон с placeholder-значениями (коммитится в git) |
| `.env` | Реальные секреты (никогда не коммитятся) |

### Dockerfile

- Базовый образ: `python:3.12-slim`
- Менеджер пакетов: `uv`
- Единый образ; `CMD` задаётся в compose отдельно для bot и web

### Сервисы docker-compose.prod.yml

**postgres:**
- Образ: `postgres:16-alpine`
- Volume: `postgres_data` (именованный Docker volume, персистентный)
- Порт: только внутренняя сеть — наружу не открывается
- `container_name: vpn-postgres` — фиксированное имя для предсказуемости команд миграции

**bot:**
- Build: `.` (Dockerfile)
- Command: `python main_bot.py`
- Зависит от: `postgres`
- Env: загружается из `.env`
- Restart: `unless-stopped`

**web:**
- Build: `.` (Dockerfile)
- Command: `uvicorn main_web:app --host 0.0.0.0 --port 8000`
- Зависит от: `postgres`
- Порт: `127.0.0.1:8000:8000` (только localhost — nginx проксирует)
- Restart: `unless-stopped`

### Изменения .env для production

`DATABASE__URL` меняется с `localhost` на имя Docker-сервиса:

```
DATABASE__URL=postgresql+asyncpg://<user>:<pass>@postgres:5432/vpn
```

Все остальные переменные остаются без изменений.

---

## Секция 2: nginx + SSL

### Установка на хост

```bash
apt install nginx certbot python3-certbot-nginx
```

### Конфиг nginx

Файл: `/etc/nginx/sites-available/vpn`

```nginx
server {
    listen 80;
    server_name <поддомен>;
    # certbot автоматически добавит редирект на HTTPS
}

server {
    listen 443 ssl;
    server_name <поддомен>;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### SSL

```bash
certbot --nginx -d <поддомен>
```

certbot модифицирует конфиг nginx: добавляет SSL-сертификат и редирект HTTP→HTTPS. Авторенью работает автоматически через systemd-таймер certbot (устанавливается по умолчанию).

### Файрволл

Открываем только порты 80 и 443. Порт 8000 остаётся закрытым снаружи — только nginx обращается к нему через localhost.

### URL webhook для YooKassa

Указать в настройках платежа: `https://<поддомен>/api/v1/yookassa/webhook`

---

## Секция 3: Runbook миграции

### Подготовка заранее (без downtime)

1. Настроить A-запись поддомена → IP сервера; дождаться распространения DNS
2. `git pull` на сервере — обновить код
3. `docker compose -f docker-compose.prod.yml build` — собрать образ заранее
4. Установить nginx, открыть порты 80/443 — не затрагивает работающий бот
5. Создать конфиг nginx, проверить `nginx -t`

### Окно миграции (~10 минут downtime)

1. `systemctl stop vpn-bot` — остановить бот
2. `pg_dump -U <pg_user> vpn > /tmp/vpn_backup_$(date +%Y%m%d).sql` — дамп базы
3. `docker compose -f docker-compose.prod.yml up -d postgres` — поднять postgres в Docker
4. Дождаться готовности postgres (healthcheck)
5. `docker exec -i vpn-postgres psql -U <pg_user> vpn < /tmp/vpn_backup_$(date +%Y%m%d).sql` — восстановить данные (имя контейнера фиксировано: `vpn-postgres`)
6. Проверить данные: количество строк в ключевых таблицах
7. `docker compose -f docker-compose.prod.yml up -d bot web` — поднять сервисы
8. `certbot --nginx -d <поддомен>` — получить SSL-сертификат
9. Проверить: бот отвечает на `/start`, `GET https://<поддомен>/health` возвращает 200
10. `systemctl disable vpn-bot` — отключить старый systemd-сервис

### Откат (если что-то пошло не так)

1. `docker compose -f docker-compose.prod.yml down`
2. `systemctl start vpn-bot` — бот сразу снова работает на нативном postgres

Нативный postgres не трогаем и не удаляем минимум неделю после успешной миграции.

---

## Вне scope

- UI панели администратора (после миграции)
- Redis FSM Storage (после миграции)
- CI/CD pipeline (пока деплой вручную)
