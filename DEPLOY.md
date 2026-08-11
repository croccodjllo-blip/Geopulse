# Deploy Centropic (`centropic.ai`)

> Ex-brand **GeoPulse** (`geopulse.it`) resta solo come alias legacy SEO/TLS:
> Nginx redirige `geopulse.it` / `www.geopulse.it` → `https://centropic.ai$request_uri`.
> Non pubblicare nuovi integrazioni o docs sotto il nome GeoPulse.

## Stack

| Componente | Come |
|---|---|
| App Flask | Gunicorn (systemd `aio-bot`) |
| DB | SQLite WAL (dev/single-worker) — **Postgres obbligatorio** per multi-worker |
| Proxy | Nginx + Let's Encrypt |
| Secrets | `/opt/aio-bot/.env` (mai in git) |
| Job worker | `aio-bot-analyze.timer` (+ kick thread in-app) |
| Rescan Plus/Business | `aio-bot-rescan.timer` |
| Backup | `aio-bot-backup.timer` |

## Database

```env
# Dev / single-node (il container Docker forza WEB_CONCURRENCY=1 con SQLite)
DATABASE_URL=sqlite:////opt/aio-bot/data/database.db

# Produzione multi-worker:
DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/centropic
WEB_CONCURRENCY=2
```

SQLite è supportato in dev (WAL + `busy_timeout` + `BEGIN IMMEDIATE` sui path critici), ma in produzione Centropic gira su **Postgres**. Cutover da SQLite: `scripts/migrate_sqlite_to_postgres.py` (dopo `create_all`/`alembic upgrade head` sul target). `ALLOW_SQLITE_PROD=1` è solo escape d’emergenza per i prod guards.

Backup giornaliero (`aio-bot-backup.timer` @ 03:15 UTC): `scripts/backup_db.py` usa `pg_dump -Fc` quando `DATABASE_URL` è Postgres (file `database-YYYYMMDD….dump`), altrimenti la copia online SQLite. Restore: `pg_restore -d centropic --no-owner database-….dump`.

### Migrazioni schema

Alembic (`alembic.ini` + `migrations/`) è la fonte di verità dello schema in produzione. Ogni deploy che include modifiche dati deve eseguire `alembic upgrade head` prima del riavvio dell'app.

`ensure_schema()` in `app.py` è mantenuto solo come bootstrap legacy additive per SQLite e ambienti di sviluppo. Non sostituisce una revisione Alembic e non è un percorso di migrazione supportato per Postgres/produzione.

## Deploy

```bash
# Codice su GitHub
git push -u origin HEAD

# Produzione: remote `vps` → hook post-receive → checkout + pip + alembic + schema check + restart
git push vps HEAD:main
```

Lo hook deve (in ordine):
1. `git checkout -f` sul work tree (`/opt/aio-bot`)
2. **`pip install -r requirements.txt`** nel venv
3. **`alembic upgrade head`** (obbligatorio — niente restart se fallisce)
4. **`python scripts/check_schema_ready.py`** (Alembic at head + index `uq_credit_ledger_stripe_pi`)
5. `systemctl restart aio-bot` **solo** se i passi sopra OK

Sample: `deploy/post-receive.sample`. Senza pip/alembic/check, non riavviare: è un deploy “cieco”.

### Fase 0 — guardrail produzione

Valori effettivi richiesti (default codice se assenti, ma vanno pinnati in `.env`):

```env
ASYNC_ANALYZE=1
ADMIN_BOOTSTRAP=0
SOV_DAILY_BUDGET_CENTS=5000   # >0; 0 = illimitato (vietato in prod)
ALLOW_DROP_ANALYSIS_JOBS=0
TRUST_PROXY=1
BEHIND_NGINX=1                 # obbligatorio se TRUST_PROXY=1
FLASK_DEBUG=0
```

Checklist systemd:

```bash
systemctl is-active aio-bot aio-bot-analyze.timer aio-bot-backup.timer aio-bot-rescan.timer
systemctl is-enabled aio-bot-analyze.timer
# Gunicorn deve restare su 127.0.0.1 (Nginx pubblico su :80/:443)
```

`/health` risponde **503** se:
- DB down
- manca l’index `uq_credit_ledger_stripe_pi`
- (con `FLASK_DEBUG=0`) falliscono i guardrail env sopra

Verifica locale/VPS:

```bash
sudo -u aio-bot .venv/bin/python scripts/verify_prod_guards.py
curl -fsS https://centropic.ai/health
```

Non pubblicare host IP, path interni o credenziali in questa guida. Usare inventory/ops privato per indirizzi e chiavi SSH.

### Env utili

```env
FLASK_SECRET_KEY=<random>
FLASK_DEBUG=0
ASYNC_ANALYZE=1
BEHIND_NGINX=1
TRUST_PROXY=1
ADMIN_BOOTSTRAP=0
ANALYZE_BATCH_LIMIT=5
JOB_STALE_HEARTBEAT_MINUTES=12
JOB_MAX_ATTEMPTS=2
MAX_CONCURRENT_ANALYZE_JOBS=2
PUBLIC_SITE_URL=https://centropic.ai
PADDLE_ENV=production
SOV_DAILY_BUDGET_CENTS=5000
ALLOW_DROP_ANALYSIS_JOBS=0
MAIL_FROM=Centropic <noreply@centropic.ai>
ADMIN_EMAIL=admin@centropic.ai
```

### Paddle Checkout — Default payment link (obbligatorio)

Senza questo, overlay/API tornano `transaction_default_checkout_url_not_set` e il checkout sembra “rotto”.

1. Apri **Paddle live** → [Checkout settings](https://vendors.paddle.com/checkout-settings)
2. **Default payment link** = `https://centropic.ai` (dominio approvato)
3. Salva, poi riprova Plus/Business su `/prezzi`

Il dominio deve essere approved in Paddle (Website approval). Webhook: `https://centropic.ai/billing/paddle-webhook`.

La `PADDLE_API_KEY` live deve includere **`transaction.write`** (oltre a read catalogo).
Senza write, il fallback server `/billing/checkout` torna 403 `forbidden`; l’overlay
Paddle.js usa solo `PADDLE_CLIENT_TOKEN` e non dipende da quel permesso.

Opzionali analytics/ads (env):

```env
# GA4_MEASUREMENT_ID=G-...
# ADS_TXT_CONTENT=...
```

### Paddle (checkout self-serve)

Senza queste chiavi `/prezzi` mostra la waitlist (`/interesse-plus`) invece del CTA Checkout.

```env
PADDLE_ENV=production
PADDLE_API_KEY=
PADDLE_CLIENT_TOKEN=
PADDLE_WEBHOOK_SECRET=
PADDLE_PRICE_PLUS_MONTHLY=
PADDLE_PRICE_BUSINESS_MONTHLY=
PADDLE_PRICE_TOPUP_1000=
PADDLE_PRICE_TOPUP_2000=
PADDLE_PRICE_TOPUP_5000=
```

Notification destination in Paddle → Developer Tools → Notifications:

- URL: `https://centropic.ai/billing/paddle-webhook`
- Eventi: `subscription.*`, `transaction.completed`, `transaction.paid`

Sandbox (`PADDLE_ENV=sandbox`) è bloccato su `PUBLIC_SITE_URL=https://centropic.ai` fuori da `FLASK_DEBUG`.

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

### Nginx e redirect brand

Vedi `deploy/nginx.prod.conf`.

| Host | Comportamento |
|---|---|
| `centropic.ai` | App (proxy → Gunicorn) |
| `www.centropic.ai` | `301` → `https://centropic.ai$request_uri` |
| `geopulse.it` | `301` → `https://centropic.ai$request_uri` |
| `www.geopulse.it` | `301` → `https://centropic.ai$request_uri` |

HTTP→HTTPS e ACME challenge restano su tutti i `server_name` del blocco `:80`.
Il certificato LE può restare multi-SAN sotto il path storico
`/etc/letsencrypt/live/geopulse.it/` finché include `centropic.ai`.

### HTTPS

Certbot con SAN per apex + www Centropic (e, finché serve, i nomi legacy GeoPulse).
Non esporre IP letterali nei `server_name` pubblici se evitabile.
