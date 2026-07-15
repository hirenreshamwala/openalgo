# Deploying the Multi-Tenant Fork on Linux

This fork adds multi-tenant SaaS behavior (user registration + admin approval,
per-user broker credentials, per-user egress proxy, admin console). It differs
from stock OpenAlgo in a few deployment-relevant ways:

- It lives on the **`feat/multitenant`** branch of **your** repo, not upstream `main`.
- It requires **`MULTI_TENANT=true`** in `.env`.
- On a **fresh** database everything is created automatically at startup. On an
  **existing** single-tenant database you must run **Alembic** once to add the
  new tables/columns.
- `frontend/dist/` **is committed on this branch**, so the server needs **no
  Node.js/npm** — a plain `git pull` ships the built UI.

Two paths below: **bare-metal (Ubuntu + gunicorn + nginx)** and **Docker**.

---

## Prerequisites (both paths)

- A Linux server (Ubuntu 22.04/24.04 recommended) with a **static public IP** — this
  is the IP each user whitelists with their broker (SEBI static-IP mandate) unless
  they configure their own egress proxy.
- A domain name pointed at the server (recommended, for HTTPS).
- Python 3.12+.

---

## Path A — Bare metal (Ubuntu, gunicorn + eventlet + nginx)

### 1. Clone your fork on the branch

```bash
sudo mkdir -p /opt/openalgo && sudo chown $USER:$USER /opt/openalgo
git clone https://github.com/hirenreshamwala/openalgo.git /opt/openalgo
cd /opt/openalgo
git checkout feat/multitenant
```

### 2. Install uv + dependencies

```bash
pip install uv
# production deps include gunicorn + eventlet
uv sync
```

### 3. Configure `.env`

```bash
cp .sample.env .env
```

Edit `.env` and set at least:

```ini
MULTI_TENANT=true

# Generate fresh secrets:
#   uv run python -c "import secrets; print(secrets.token_hex(32))"
APP_KEY = '<generated>'
API_KEY_PEPPER = '<generated>'

# Public URL of this server — used to build each user's broker redirect URL
# ({HOST_SERVER}/{broker}/callback) dynamically. No trailing slash.
HOST_SERVER = 'https://your-domain.com'

# Multi-tenant builds the real redirect per broker at runtime, so this stays a
# placeholder (the startup check skips it when MULTI_TENANT=true):
REDIRECT_URL = 'https://your-domain.com/<broker>/callback'

# Bind for gunicorn behind nginx:
FLASK_HOST_IP = '127.0.0.1'
FLASK_PORT = '5000'

# Enable the brokers you allow users to connect:
VALID_BROKERS = 'zerodha,dhan,angel,upstox,fyers'   # etc.

# Behind nginx, trust forwarded IPs so real client IPs are logged:
TRUST_PROXY_HEADERS = 'TRUE'
```

> The port-5000 vs 5001 issue you hit locally was **macOS AirPlay** only — on Linux, 5000 is fine.

### 4. Database

**Fresh install (new DB):** nothing to do — the app self-creates all tables
(including the multi-tenant ones) on first start because `MULTI_TENANT=true`.
Optionally mark the schema current so future migrations don't replay:

```bash
uv run alembic stamp head
```

**Upgrading an existing single-tenant OpenAlgo DB:** run the migrations once to add
the new tables/columns (user status/role, user_broker_credentials incl. proxy_url,
symbols/broker_symbols):

```bash
uv run alembic upgrade head
```

> SQLite is fine to start. For many concurrent users, point `DATABASE_URL` at
> PostgreSQL (`postgresql+psycopg://user:pass@localhost/openalgo`) and run
> `alembic upgrade head` against it.

### 5. Run under gunicorn (eventlet, single worker)

```bash
uv run gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 --timeout 300 app:app
```

`-w 1` is **required** (WebSocket/SocketIO state is in-process).

### 6. systemd service (keeps it running)

Create `/etc/systemd/system/openalgo.service`:

```ini
[Unit]
Description=OpenAlgo (multi-tenant)
After=network.target

[Service]
User=youruser
WorkingDirectory=/opt/openalgo
ExecStart=/home/youruser/.local/bin/uv run gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 --timeout 300 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now openalgo
sudo systemctl status openalgo
```

### 7. nginx reverse proxy + WebSocket

Create `/etc/nginx/sites-available/openalgo` (proxies the app **and** the
WebSocket feed on 8765):

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Unified WebSocket market-data feed
    location /ws {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/openalgo /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 8. HTTPS (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 9. First run

1. Visit `https://your-domain.com/setup` → create the **admin** account.
2. Log in → you land on the **admin console** (`/admin/mt/users`).
3. Users self-register at `/auth/register`; approve them in the console.
4. Each user adds their broker API key/secret (and optional egress proxy) at
   `/mt/broker-credentials`, then connects at `/broker`.

---

## Path B — Docker

```bash
git clone https://github.com/hirenreshamwala/openalgo.git /opt/openalgo
cd /opt/openalgo && git checkout feat/multitenant
cp .sample.env .env      # then edit as in step 3 above (MULTI_TENANT=true, keys, HOST_SERVER)
docker compose up -d --build
docker compose logs -f
```

For an **existing** DB being upgraded, run migrations inside the container once:

```bash
docker compose exec openalgo /app/.venv/bin/alembic upgrade head
```

The container entrypoint (`start.sh`) already runs gunicorn with
`--worker-class eventlet --workers 1`. Put nginx/Caddy in front for TLS, or use
`install/install-docker.sh` which wires nginx + certbot for you.

---

## Upgrades (after the first deploy)

```bash
cd /opt/openalgo
git pull                       # brings latest code + prebuilt frontend/dist
uv sync                        # if deps changed
uv run alembic upgrade head    # if new migrations were added
sudo systemctl restart openalgo
```

---

## Multi-tenant checklist

- [ ] `MULTI_TENANT=true`
- [ ] Fresh secrets for `APP_KEY` and `API_KEY_PEPPER`
- [ ] `HOST_SERVER` = your public HTTPS URL (no trailing slash)
- [ ] Migrations applied (`alembic upgrade head`) **only** if upgrading an existing DB
- [ ] gunicorn `--worker-class eventlet -w 1`
- [ ] nginx proxies both `/` (5000) and `/ws` (8765)
- [ ] Server's static IP shown on `/mt/broker-credentials` — users whitelist it
      (or their own proxy IP) with their broker
