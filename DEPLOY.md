# Deploy Centropic / GeoPulse

## Stack

| Componente | Come |
|---|---|
| App Flask | Gunicorn (systemd `aio-bot`) |
| DB | SQLite WAL (default) — **prefer Postgres** via `DATABASE_URL` in produzione multi-worker |
| Proxy | Nginx + Let's Encrypt |
| Secrets | `/opt/aio-bot/.env` (mai in git) |
| Job worker | `aio-bot-analyze.timer` (+ kick thread in-app) |
| Rescan Pro | `aio-bot-rescan.timer` |
| Backup | `aio-bot-backup.timer` |

## Database

```env
# Dev / single-node
DATABASE_URL=sqlite:////opt/aio-bot/data/database.db

# Consigliato in produzione (multi-worker):
# DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/centropic
```

SQLite è supportato (WAL + `busy_timeout` + `BEGIN IMMEDIATE` sui path critici), ma per crescita SaaS usare Postgres.

## Deploy

```bash
# Codice su GitHub
git push -u origin HEAD

# Produzione: remote `vps` → hook post-receive → checkout + pip + restart
git push vps HEAD:main
```

Lo hook deve:
1. `git checkout -f` sul work tree (`/opt/aio-bot`)
2. **`pip install -r requirements.txt`** nel venv (obbligatorio dopo dipendenze nuove)
3. `systemctl restart aio-bot`

Sample: `deploy/post-receive.sample`. Senza lo step pip, import nuovi falliscono in silenzio fino al restart con moduli mancanti.

Non pubblicare host IP, path interni o credenziali in questa guida. Usare inventory/ops privato per indirizzi e chiavi SSH.

### Env utili

```env
FLASK_SECRET_KEY=<random>
FLASK_DEBUG=0
ASYNC_ANALYZE=1
ANALYZE_BATCH_LIMIT=5
JOB_STALE_HEARTBEAT_MINUTES=12
JOB_MAX_ATTEMPTS=2
MAX_CONCURRENT_ANALYZE_JOBS=2
PUBLIC_SITE_URL=https://centropic.ai
ADMIN_EMAIL=admin@centropic.ai
# Opzionali analytics/ads:
# GA4_MEASUREMENT_ID=G-...
# ADS_TXT_CONTENT=...
```

### Worker analyze

```bash
sudo systemctl enable --now aio-bot-analyze.timer
sudo -u aio-bot .venv/bin/python scripts/analyze_worker.py -v
```

### i18n (dopo edit template con `_()`)

```bash
python scripts/i18n_auto_translate.py
```

Admin UI resta in italiano di proposito (non wrappata).

### Nginx

Vedi `deploy/nginx.prod.conf`. **www → apex** obbligatorio:

```nginx
if ($host = www.centropic.ai) { return 301 https://centropic.ai$request_uri; }
if ($host = www.geopulse.it)  { return 301 https://geopulse.it$request_uri; }
```

### HTTPS

Certbot con SAN per apex + www. Non esporre IP letterali nei `server_name` pubblici se evitabile.
