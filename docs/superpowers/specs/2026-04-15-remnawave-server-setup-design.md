# Remnawave Panel — Пошаговый план установки

**Дата:** 2026-04-15
**Сервер панели:** 62.133.60.207
**Домен:** заменить `YOURDOMAIN` на свой во всех командах

---

## Архитектура

```
Internet (443)
    ↓
Nginx (Docker, remnawave-network)
    ├── panel.YOURDOMAIN  → remnawave:3000
    └── sub.YOURDOMAIN    → remnawave-subscription-page:3010

Docker Compose /opt/remnawave/:
    remnawave                  (порт 3000, только внутри сети)
    remnawave-db               (PostgreSQL, только внутри сети)
    remnawave-redis            (Redis, только внутри сети)

Docker Compose /opt/remnawave/subscription/:
    remnawave-subscription-page (порт 3010, только внутри сети)

Docker Compose /opt/remnawave/nginx/:
    remnawave-nginx            (порт 443, смотрит наружу)
```

---

## DNS (настроить до установки)

У регистратора добавить A-записи:

| Тип | Имя | Значение | Proxy |
|-----|-----|----------|-------|
| A | `panel` | `62.133.60.207` | DNS only (серый) |
| A | `sub` | `62.133.60.207` | DNS only (серый) |

**Cloudflare proxy должен быть выключен** — несовместим с Remnawave.

Подождать пока DNS пропагируется (обычно 5-10 минут).

---

## Шаг 1 — Docker

```bash
sudo curl -fsSL https://get.docker.com | sh
```

---

## Шаг 2 — Firewall

```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## Шаг 3 — SSL-сертификаты (acme.sh)

```bash
sudo apt-get install -y cron socat
curl https://get.acme.sh | sh -s email=YOUR@EMAIL.COM
source ~/.bashrc

mkdir -p /opt/remnawave/nginx

# Сертификат для панели
acme.sh --issue --standalone \
  -d 'panel.zevsgate.com' \
  --key-file /opt/remnawave/nginx/panel.privkey.key \
  --fullchain-file /opt/remnawave/nginx/panel.fullchain.pem \
  --alpn --tlsport 8443

# Сертификат для subscription page
acme.sh --issue --standalone \
  -d 'sub.zevsgate.com' \
  --key-file /opt/remnawave/nginx/sub.privkey.key \
  --fullchain-file /opt/remnawave/nginx/sub.fullchain.pem \
  --alpn --tlsport 8443
```

---

## Шаг 4 — Remnawave Panel

```bash
mkdir -p /opt/remnawave && cd /opt/remnawave

curl -o docker-compose.yml \
  https://raw.githubusercontent.com/remnawave/backend/refs/heads/main/docker-compose-prod.yml

curl -o .env \
  https://raw.githubusercontent.com/remnawave/backend/refs/heads/main/.env.sample
```

Сгенерировать секреты:

```bash
sed -i "s/^JWT_AUTH_SECRET=.*/JWT_AUTH_SECRET=$(openssl rand -hex 64)/" .env
sed -i "s/^JWT_API_TOKENS_SECRET=.*/JWT_API_TOKENS_SECRET=$(openssl rand -hex 64)/" .env
sed -i "s/^METRICS_PASS=.*/METRICS_PASS=$(openssl rand -hex 64)/" .env
sed -i "s/^WEBHOOK_SECRET_HEADER=.*/WEBHOOK_SECRET_HEADER=$(openssl rand -hex 64)/" .env
pw=$(openssl rand -hex 24) \
  && sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$pw/" .env \
  && sed -i "s|^\(DATABASE_URL=\"postgresql://postgres:\)[^\@]*\(@.*\)|\1$pw\2|" .env
```

Вручную отредактировать `.env`:

```bash
nano .env
```

Найти и заменить:
```
PANEL_DOMAIN=panel.YOURDOMAIN
FRONT_END_DOMAIN=panel.YOURDOMAIN
SUB_PUBLIC_DOMAIN=sub.YOURDOMAIN
```

Запустить:

```bash
docker compose up -d && docker compose logs -f -t
# Ctrl+C когда убедишься что запустился без ошибок
```

---

## Шаг 5 — Subscription Page

```bash
mkdir -p /opt/remnawave/subscription && cd /opt/remnawave/subscription
```

Создать `docker-compose.yml`:

```yaml
services:
  remnawave-subscription-page:
    image: remnawave/subscription-page:latest
    container_name: remnawave-subscription-page
    hostname: remnawave-subscription-page
    restart: always
    env_file:
      - .env
    ports:
      - '127.0.0.1:3010:3010'
    networks:
      - remnawave-network

networks:
  remnawave-network:
    name: remnawave-network
    driver: bridge
    external: true
```

Создать `.env`:

```
APP_PORT=3010
REMNAWAVE_PANEL_URL=https://panel.YOURDOMAIN
REMNAWAVE_API_TOKEN=ВСТАВИТЬ_ПОСЛЕ_ШАГА_7
```

Запустить пока без токена (добавим после):

```bash
docker compose up -d
```

---

## Шаг 6 — Nginx (reverse proxy для обоих)

```bash
cd /opt/remnawave/nginx
```

Создать `nginx.conf`:

```nginx
upstream remnawave {
    server remnawave:3000;
}

upstream remnawave-sub {
    server remnawave-subscription-page:3010;
}

# panel.YOURDOMAIN → панель управления
server {
    server_name panel.zevsgate.com;
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;

    ssl_certificate     /etc/nginx/ssl/panel.fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/panel.privkey.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:MozSSL:10m;
    ssl_session_tickets off;

    location / {
        proxy_http_version 1.1;
        proxy_pass http://remnawave;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# sub.YOURDOMAIN → subscription page
server {
    server_name sub.zevsgate.com;
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;

    ssl_certificate     /etc/nginx/ssl/sub.fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/sub.privkey.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:MozSSL:10m;
    ssl_session_tickets off;

    location / {
        proxy_http_version 1.1;
        proxy_pass http://remnawave-sub;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Отклонять все остальные запросы на 443
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    ssl_reject_handshake on;
}
```

Создать `docker-compose.yml`:

```yaml
services:
  remnawave-nginx:
    image: nginx:1.28
    container_name: remnawave-nginx
    hostname: remnawave-nginx
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./panel.fullchain.pem:/etc/nginx/ssl/panel.fullchain.pem:ro
      - ./panel.privkey.key:/etc/nginx/ssl/panel.privkey.key:ro
      - ./sub.fullchain.pem:/etc/nginx/ssl/sub.fullchain.pem:ro
      - ./sub.privkey.key:/etc/nginx/ssl/sub.privkey.key:ro
    restart: always
    ports:
      - '0.0.0.0:443:443'
    networks:
      - remnawave-network

networks:
  remnawave-network:
    name: remnawave-network
    driver: bridge
    external: true
```

Запустить:

```bash
docker compose up -d && docker compose logs -f -t
```

Проверить что панель открывается: `https://panel.YOURDOMAIN`

---

## Шаг 7 — Получить API-токен

1. Зайти в `https://panel.YOURDOMAIN`
2. Зарегистрировать аккаунт администратора
3. Перейти в **Settings → API Tokens**
4. Создать новый токен
5. Скопировать токен

Вставить токен в subscription page:

```bash
nano /opt/remnawave/subscription/.env
# REMNAWAVE_API_TOKEN=вставить_токен
```

Перезапустить subscription page:

```bash
cd /opt/remnawave/subscription && docker compose restart
```

---

## Шаг 8 — Проверка

1. Создать тестового пользователя в панели
2. Скопировать его `subscription URL` (вида `https://sub.YOURDOMAIN/XXXXX`)
3. Открыть в Hiddify или v2rayNG
4. Убедиться что видны серверы и соединение работает

---

## Шаг 9 — Node (89.23.108.122, повторить для каждой ноды)

```bash
# На сервере ноды:
sudo curl -fsSL https://get.docker.com | sh

ufw allow 22/tcp
ufw allow 443/tcp
ufw allow 2222/tcp  # gRPC только от IP панели (настроить отдельно)
ufw enable

mkdir /opt/remnanode && cd /opt/remnanode
```

Создать `docker-compose.yml` (заполнить SECRET_KEY):

```yaml
services:
  remnawave-node:
    image: remnawave/node:latest
    container_name: remnawave-node
    hostname: remnawave-node
    restart: always
    network_mode: host
    environment:
      - NODE_PORT=2222
      - SECRET_KEY=СГЕНЕРИРОВАТЬ_СЛОЖНЫЙ_КЛЮЧ
    volumes:
      - /var/log/remnanode:/var/log/remnanode
```

```bash
docker compose up -d && docker compose logs -f -t
```

После запуска — добавить ноду в панели: **Nodes → Add Node**, указать IP и SECRET_KEY.

---

## После успешной проверки — переходим к Этапу 2 миграции бота

- Добавить `RemnawaveSettings(url, token)` в конфиг бота
- Написать `src/infrastructure/remnawave/client.py`
- Начать новую доменную модель подписки

См. `docs/migration-remnawave.md` для полного плана.
