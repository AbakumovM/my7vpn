# Docker Deployment Design

**Date:** 2026-04-27
**Status:** Approved

---

## Context

The bot currently runs as a systemd service on a bare server with a native Postgres instance. There is no Dockerfile, no reverse proxy, and the web service is not publicly accessible. YooKassa webhooks require HTTPS, which is not yet configured.

Goal: migrate the full stack to Docker Compose with nginx + Let's Encrypt on the host, preserving the existing database, with ~10 minutes of downtime during the migration window.

---

## Architecture

**Approach:** Docker Compose for application services (postgres, bot, web) + nginx natively on the host as reverse proxy with SSL termination.

```
Internet
   │
   ▼
nginx (host, port 80/443)
   │ proxy_pass 127.0.0.1:8000
   ▼
[web container] uvicorn :8000
   │
   └──────────────────────────┐
                              ▼
[bot container]  ──────► [postgres container] :5432 (internal network only)
```

---

## Section 1: Docker Infrastructure

### Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Single image for bot and web services |
| `docker-compose.yml` | Local dev: postgres + pgadmin only (unchanged) |
| `docker-compose.prod.yml` | Production: postgres + bot + web |
| `.env.example` | Template with placeholder values (committed to git) |
| `.env` | Real secrets (never committed) |

### Dockerfile

- Base: `python:3.12-slim`
- Package manager: `uv`
- Single image; `CMD` differs per service in compose

### docker-compose.prod.yml services

**postgres:**
- Image: `postgres:16-alpine`
- Volume: `postgres_data` (named Docker volume, persistent)
- Port: internal network only — not exposed to host
- `container_name: vpn-postgres` — explicit name so migration commands are predictable

**bot:**
- Build: `.` (Dockerfile)
- Command: `python main_bot.py`
- Depends on: `postgres`
- Env: loaded from `.env`
- Restart: `unless-stopped`

**web:**
- Build: `.` (Dockerfile)
- Command: `uvicorn main_web:app --host 0.0.0.0 --port 8000`
- Depends on: `postgres`
- Port: `127.0.0.1:8000:8000` (localhost only — nginx proxies to it)
- Restart: `unless-stopped`

### .env changes for production

`DATABASE__URL` must use the Docker service name instead of `localhost`:

```
DATABASE__URL=postgresql+asyncpg://<user>:<pass>@postgres:5432/vpn
```

All other variables remain the same.

---

## Section 2: nginx + SSL

### Installation (on host)

```bash
apt install nginx certbot python3-certbot-nginx
```

### nginx config

File: `/etc/nginx/sites-available/vpn`

```nginx
server {
    listen 80;
    server_name <subdomain>;
    # certbot adds HTTPS redirect automatically
}

server {
    listen 443 ssl;
    server_name <subdomain>;

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
certbot --nginx -d <subdomain>
```

certbot modifies the nginx config to add SSL certificates and HTTP→HTTPS redirect. Auto-renewal is handled by certbot's systemd timer (installed by default).

### Firewall

Open only ports 80 and 443. Port 8000 stays closed to external traffic — only nginx accesses it via localhost.

### YooKassa webhook URL

Set in YooKassa dashboard: `https://<subdomain>/api/v1/yookassa/webhook`

---

## Section 3: Migration Runbook

### Pre-migration (do in advance, no downtime)

1. Point subdomain A record → server IP; wait for DNS propagation
2. `git pull` latest code on server
3. `docker compose -f docker-compose.prod.yml build` — pre-build image
4. Install nginx on host, open ports 80/443 — does not affect running bot
5. Create nginx config, run `nginx -t` to verify syntax

### Migration window (~10 min downtime)

1. `systemctl stop vpn-bot` — stop current bot
2. `pg_dump -U <pg_user> vpn > /tmp/vpn_backup_$(date +%Y%m%d).sql` — dump database
3. `docker compose -f docker-compose.prod.yml up -d postgres` — start postgres container
4. Wait for postgres to be ready (health check)
5. `docker exec -i vpn-postgres psql -U <pg_user> vpn < /tmp/vpn_backup_$(date +%Y%m%d).sql` — restore data (container name is fixed as `vpn-postgres`)
6. Verify data: spot-check row counts in key tables
7. `docker compose -f docker-compose.prod.yml up -d bot web` — start application containers
8. `certbot --nginx -d <subdomain>` — obtain SSL certificate
9. Test: bot responds to `/start`, `GET https://<subdomain>/health` returns 200
10. `systemctl disable vpn-bot` — disable old systemd service

### Rollback (if anything goes wrong)

1. `docker compose -f docker-compose.prod.yml down`
2. `systemctl start vpn-bot` — bot is back on native postgres immediately
3. Native postgres is untouched and available as fallback

Keep native postgres running for at least one week after successful migration before removing it.

---

## Out of Scope

- Admin panel UI (post-migration work)
- Redis FSM storage (post-migration work)
- CI/CD pipeline (manual deploy for now)
