# Docker Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Цель:** Перенести бот и веб-сервис в Docker Compose с nginx + Let's Encrypt на хосте, сохранив существующую базу данных.

**Архитектура:** Три Docker-сервиса (postgres, bot, web) в `docker-compose.prod.yml`. nginx устанавливается нативно на хост, терминирует SSL и проксирует входящие запросы на `127.0.0.1:8000` (контейнер web). Бот и веб используют один Docker-образ с разными командами запуска.

**Стек:** Python 3.12, uv, Docker Compose, nginx, certbot (Let's Encrypt), PostgreSQL 16.

---

## Задача 1: Создать Dockerfile

**Файлы:**
- Создать: `Dockerfile`

Один образ для обоих сервисов (bot и web). Точка входа задаётся через `command:` в compose-файле.

- [ ] **Шаг 1: Создать Dockerfile**

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Копируем файлы зависимостей отдельно для кэширования слоя
COPY pyproject.toml uv.lock ./

# Устанавливаем только prod-зависимости из lockfile
RUN uv sync --no-dev --frozen

# Копируем весь исходный код
COPY . .

# Добавляем venv в PATH
ENV PATH="/app/.venv/bin:$PATH"
```

- [ ] **Шаг 2: Убедиться что образ собирается**

```bash
docker build -t vpn-bot-test .
```

Ожидаемый результат: `Successfully built <id>` без ошибок.

- [ ] **Шаг 3: Убедиться что оба entry point запускаются**

```bash
docker run --rm vpn-bot-test python -c "import main_bot; print('bot ok')"
docker run --rm vpn-bot-test python -c "import main_web; print('web ok')"
```

Ожидаемый результат: обе команды печатают `ok` (могут быть ошибки конфигурации — это ок, импорт должен работать).

- [ ] **Шаг 4: Удалить тестовый образ**

```bash
docker rmi vpn-bot-test
```

- [ ] **Шаг 5: Закоммитить**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile for bot and web services"
```

---

## Задача 2: Создать docker-compose.prod.yml

**Файлы:**
- Создать: `docker-compose.prod.yml`

Три сервиса: postgres (с healthcheck), bot, web. Порт postgres не открывается наружу. Веб-сервис слушает только на localhost.

- [ ] **Шаг 1: Создать docker-compose.prod.yml**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: vpn-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - vpn-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

  bot:
    build: .
    container_name: vpn-bot
    command: python main_bot.py
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - vpn-net
    restart: unless-stopped

  web:
    build: .
    container_name: vpn-web
    command: uvicorn main_web:app --host 0.0.0.0 --port 8000
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "127.0.0.1:8000:8000"
    networks:
      - vpn-net
    restart: unless-stopped

networks:
  vpn-net:

volumes:
  postgres_data:
```

- [ ] **Шаг 2: Проверить синтаксис compose-файла**

Для проверки нужны переменные POSTGRES_USER/PASSWORD/DB. Создаём временный файл:

```bash
POSTGRES_USER=test POSTGRES_PASSWORD=test POSTGRES_DB=test \
  docker compose -f docker-compose.prod.yml config
```

Ожидаемый результат: вывод полного merged конфига без ошибок.

- [ ] **Шаг 3: Закоммитить**

```bash
git add docker-compose.prod.yml
git commit -m "feat: add production docker-compose"
```

---

## Задача 3: Создать .env.example и обновить .gitignore

**Файлы:**
- Создать: `.env.example`
- Изменить: `.gitignore`

`.env.example` — шаблон для создания `.env` на сервере. Все реальные значения заменены на placeholder'ы. `DATABASE__URL` уже содержит правильный хост (`postgres` — имя Docker-сервиса).

Важно: `LOGGING__LOG_TO_FILE=false` — в Docker логи идут в stdout, читаются через `docker compose logs`.

- [ ] **Шаг 1: Создать .env.example**

```bash
cat > .env.example << 'EOF'
# Telegram Bot
BOT__TOKEN=1234567890:AABBCCDDEEFFaabbccddeeff-1234567890
BOT__ADMIN_ID=123456789
BOT__BOT_NAME=your_bot_username

# База данных (хост — имя сервиса postgres в Docker Compose)
DATABASE__URL=postgresql+asyncpg://vpnuser:strongpassword@postgres:5432/vpn

# Переменные для postgres-контейнера (должны совпадать с DATABASE__URL)
POSTGRES_USER=vpnuser
POSTGRES_PASSWORD=strongpassword
POSTGRES_DB=vpn

# Оплата
PAYMENT__PAYMENT_URL=https://example.com/pay
PAYMENT__PAYMENT_QR=image/qr_payment.jpeg
PAYMENT__FREE_MONTH=30

# Логирование (в Docker используем stdout, файлы не нужны)
LOGGING__LOG_LEVEL=INFO
LOGGING__LOG_JSON=true
LOGGING__LOG_TO_FILE=false

# Remnawave
REMNAWAVE__URL=https://your-panel.domain.com
REMNAWAVE__TOKEN=your_remnawave_jwt_token
REMNAWAVE__DEFAULT_SQUAD_UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# YooKassa
YOOKASSA__ENABLED=true
YOOKASSA__SHOP_ID=1234567
YOOKASSA__SECRET_KEY=live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
YOOKASSA__RETURN_URL=https://t.me/your_bot_username

# Авторизация (JWT для веб-кабинета)
AUTH__JWT_SECRET=change-me-to-random-64-char-string
AUTH__SITE_URL=https://your.domain.com
EOF
```

- [ ] **Шаг 2: Добавить logs/ в .gitignore**

В `.gitignore` добавить строку после `*.log`:

```
logs/
```

- [ ] **Шаг 3: Закоммитить**

```bash
git add .env.example .gitignore
git commit -m "feat: add .env.example and ignore logs directory"
```

---

## Задача 4: Создать nginx конфиг в репозитории

**Файлы:**
- Создать: `deploy/nginx.conf`

Конфиг хранится в репозитории как reference — на сервере он копируется в `/etc/nginx/sites-available/vpn`. Certbot после запуска автоматически добавит блок SSL и редирект HTTP→HTTPS — вручную их прописывать не нужно.

- [ ] **Шаг 1: Создать директорию deploy и конфиг**

```bash
mkdir -p deploy
```

Создать файл `deploy/nginx.conf`:

```nginx
server {
    listen 80;
    server_name YOUR_SUBDOMAIN_HERE;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Примечание: `YOUR_SUBDOMAIN_HERE` заменяется на реальный поддомен при копировании на сервер. Блок `listen 443 ssl` добавляет certbot автоматически.

- [ ] **Шаг 2: Закоммитить**

```bash
git add deploy/nginx.conf
git commit -m "feat: add nginx config reference for deployment"
```

---

## Задача 5: Запушить изменения на GitHub

- [ ] **Шаг 1: Убедиться что все изменения закоммичены**

```bash
git status
```

Ожидаемый результат: `nothing to commit, working tree clean`

- [ ] **Шаг 2: Запушить ветку**

```bash
git push origin refactoring
```

Или если деплоим из `main`:

```bash
git checkout main
git merge refactoring
git push origin main
```

---

## Задача 6: Подготовить сервер — Docker, nginx, certbot

> Выполняется на сервере. Без downtime, можно делать днём.

**Предварительно:** Настрой A-запись поддомена в DNS (например `vpn.example.com → IP сервера`). DNS может распространяться до 24 часов — делай заранее.

- [ ] **Шаг 1: Обновить систему**

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

- [ ] **Шаг 2: Установить Docker**

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

Проверить:

```bash
docker --version
```

Ожидаемый результат: `Docker version 24.x.x` или новее.

- [ ] **Шаг 3: Установить Docker Compose plugin**

Docker Compose обычно устанавливается вместе с Docker (как плагин). Проверить:

```bash
docker compose version
```

Ожидаемый результат: `Docker Compose version v2.x.x`. Если команда не найдена:

```bash
sudo apt-get install -y docker-compose-plugin
```

- [ ] **Шаг 4: Установить nginx и certbot**

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

- [ ] **Шаг 5: Открыть порты 80 и 443 в файрволле**

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

Ожидаемый результат: в списке правил есть строки для 80 и 443.

Если ufw не активирован:

```bash
sudo ufw enable
```

---

## Задача 7: Развернуть код и настроить nginx на сервере

> Выполняется на сервере. Без downtime, можно делать днём.

- [ ] **Шаг 1: Клонировать/обновить репозиторий**

Если репозиторий ещё не клонирован:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git /opt/vpn-bot
cd /opt/vpn-bot
```

Если уже есть:

```bash
cd /opt/vpn-bot  # или путь где лежит код
git pull origin main
```

- [ ] **Шаг 2: Создать .env на сервере**

```bash
cp .env.example .env
nano .env
```

Заполнить все значения:
- `DATABASE__URL` — хост `postgres` (уже правильный в примере)
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — те же credentials что в `DATABASE__URL`
- `BOT__TOKEN` — токен бота
- `BOT__ADMIN_ID` — твой Telegram ID
- `REMNAWAVE__*` — данные Remnawave панели
- `YOOKASSA__*` — ключи YooKassa
- `AUTH__JWT_SECRET` — случайная строка 64+ символа: `openssl rand -hex 32`
- `AUTH__SITE_URL` — `https://YOUR_SUBDOMAIN_HERE`

- [ ] **Шаг 3: Собрать Docker-образ**

```bash
docker compose -f docker-compose.prod.yml build
```

Ожидаемый результат: `Successfully built` в конце.

- [ ] **Шаг 4: Настроить nginx**

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/vpn
sudo nano /etc/nginx/sites-available/vpn
```

Заменить `YOUR_SUBDOMAIN_HERE` на реальный поддомен (например `vpn.example.com`).

```bash
sudo ln -s /etc/nginx/sites-available/vpn /etc/nginx/sites-enabled/vpn
sudo nginx -t
```

Ожидаемый результат: `syntax is ok` и `test is successful`.

```bash
sudo systemctl reload nginx
```

- [ ] **Шаг 5: Убедиться что DNS propagation прошёл**

```bash
curl http://YOUR_SUBDOMAIN_HERE/health
```

Если DNS ещё не распространился, команда вернёт ошибку подключения. Дождись успешного curl перед следующим шагом.

---

## Задача 8: Runbook миграции (ночью, ~10 минут downtime)

> Выполняется на сервере ночью. Порядок шагов критичен.

- [ ] **Шаг 1: Остановить текущий бот**

```bash
sudo systemctl stop vpn-bot
```

Убедиться что процесс остановлен:

```bash
sudo systemctl status vpn-bot
```

Ожидаемый результат: `Active: inactive (dead)`.

- [ ] **Шаг 2: Сделать дамп существующей базы**

```bash
pg_dump -U mihailabakumov vpn > /tmp/vpn_backup_$(date +%Y%m%d_%H%M).sql
ls -lh /tmp/vpn_backup_*.sql
```

Ожидаемый результат: файл размером больше нескольких KB (не пустой).

- [ ] **Шаг 3: Поднять postgres-контейнер**

```bash
cd /opt/vpn-bot  # или путь к репозиторию
docker compose -f docker-compose.prod.yml up -d postgres
```

Подождать пока healthcheck пройдёт:

```bash
docker compose -f docker-compose.prod.yml ps
```

Ожидаемый результат: статус postgres — `healthy`.

- [ ] **Шаг 4: Убедиться что база создана в контейнере**

Postgres автоматически создаёт базу из `POSTGRES_DB` при первом запуске. Проверяем:

```bash
# Считай значение POSTGRES_USER из .env
PGUSER=$(grep '^POSTGRES_USER=' .env | cut -d= -f2)
docker exec -it vpn-postgres psql -U "$PGUSER" -c "\l" postgres
```

Ожидаемый результат: в списке баз есть `vpn`.

- [ ] **Шаг 5: Импортировать дамп**

```bash
PGUSER=$(grep '^POSTGRES_USER=' .env | cut -d= -f2)
docker exec -i vpn-postgres psql -U "$PGUSER" vpn < /tmp/vpn_backup_$(ls -t /tmp/vpn_backup_*.sql | head -1 | xargs basename)
```

Ожидаемый результат: много строк вывода (`INSERT`, `CREATE TABLE`, etc.) без ошибок типа `ERROR`.

- [ ] **Шаг 6: Проверить данные**

```bash
PGUSER=$(grep '^POSTGRES_USER=' .env | cut -d= -f2)
docker exec -it vpn-postgres psql -U "$PGUSER" vpn -c "\dt"
docker exec -it vpn-postgres psql -U "$PGUSER" vpn -c "SELECT COUNT(*) FROM users;"
```

Ожидаемый результат: список таблиц и количество пользователей совпадает с тем что было до миграции.

- [ ] **Шаг 7: Применить миграции Alembic**

Запускаем временный контейнер на основе образа бота:

```bash
docker compose -f docker-compose.prod.yml run --rm bot alembic upgrade head
```

Ожидаемый результат: `INFO  [alembic.runtime.migration] Running upgrade ...` и завершение без ошибок.

- [ ] **Шаг 8: Запустить бот и веб-сервис**

```bash
docker compose -f docker-compose.prod.yml up -d bot web
```

Проверить что контейнеры запустились:

```bash
docker compose -f docker-compose.prod.yml ps
```

Ожидаемый результат: все три сервиса в статусе `running`.

- [ ] **Шаг 9: Получить SSL-сертификат**

```bash
sudo certbot --nginx -d YOUR_SUBDOMAIN_HERE
```

certbot спросит email (для уведомлений об истечении) и предложит редирект HTTP→HTTPS — выбери Yes.

Ожидаемый результат: `Successfully deployed certificate` в конце.

- [ ] **Шаг 10: Проверить работу**

```bash
curl https://YOUR_SUBDOMAIN_HERE/health
```

Ожидаемый результат: `{"status": "ok"}`

Проверить бот: отправить `/start` в Telegram — бот должен ответить.

Проверить логи:

```bash
docker compose -f docker-compose.prod.yml logs --tail=50 bot
docker compose -f docker-compose.prod.yml logs --tail=50 web
```

- [ ] **Шаг 11: Обновить URL webhook в YooKassa**

В личном кабинете YooKassa → Настройки → Уведомления:

```
https://YOUR_SUBDOMAIN_HERE/api/v1/yookassa/webhook
```

- [ ] **Шаг 12: Отключить старый systemd-сервис**

```bash
sudo systemctl disable vpn-bot
```

Нативный postgres **не трогаем** — оставить как fallback минимум на неделю. Удалить можно командой `sudo apt-get remove postgresql` после того как убедишься что всё работает стабильно.

---

### Откат (если что-то пошло не так на любом шаге)

```bash
# Остановить Docker-контейнеры
docker compose -f docker-compose.prod.yml down

# Вернуть бот на нативный postgres
sudo systemctl start vpn-bot
sudo systemctl status vpn-bot  # должен быть active (running)
```

Нативный postgres всё это время работал и не был затронут — бот сразу возобновит работу.

---

## Справочные команды для управления после деплоя

```bash
# Посмотреть статус всех сервисов
docker compose -f docker-compose.prod.yml ps

# Посмотреть логи бота в реальном времени
docker compose -f docker-compose.prod.yml logs -f bot

# Перезапустить бот без downtime
docker compose -f docker-compose.prod.yml restart bot

# Обновить код и перезапустить (новый деплой)
git pull origin main
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d --no-deps bot web

# Войти в контейнер для отладки
docker exec -it vpn-bot bash

# Сделать backup базы из контейнера
docker exec vpn-postgres pg_dump -U vpnuser vpn > /tmp/backup_$(date +%Y%m%d).sql
```
