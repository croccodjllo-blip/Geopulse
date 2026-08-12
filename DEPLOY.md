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
| Job worker | `aio-bot-analyze.service` (Type=simple `--loop`) + optional Redis LIST dispatch + timer oneshot backup |
| Redis (optional) | `REDIS_URL` — analyze queue + shared LLM RPM/TPM |
| S3 packs (optional) | `ANALYZE_ARTIFACT_STORE=s3` + `ANALYZE_S3_BUCKET` |
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
systemctl is-active aio-bot aio-bot-analyze.service aio-bot-analyze.timer aio-bot-backup.timer aio-bot-rescan.timer
systemctl is-enabled aio-bot-analyze.service aio-bot-analyze.timer
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
MAX_RUNNING_ANALYZE_JOBS=100
ANALYZE_WORKER_CONCURRENCY=50
ANALYZE_WORKER_IDLE_SLEEP=2
MAX_CONCURRENT_ANALYZE_FREE=1
MAX_CONCURRENT_ANALYZE_PLUS=3
MAX_CONCURRENT_ANALYZE_BUSINESS=5
MAX_CONCURRENT_ANALYZE_ADMIN=8
MAX_CONCURRENT_ANALYZE_JOBS=2
MAX_CONCURRENT_MEASURED=16
MEASURED_SHED_ENABLE=1
MEASURED_SHED_QUEUE_DEPTH=40
DB_POOL_SIZE=100
DB_MAX_OVERFLOW=120
OPENAI_RPM=120
PERPLEXITY_RPM=60
ANTHROPIC_RPM=60
REDIS_URL=redis://127.0.0.1:6379/0
ANALYZE_QUEUE_BACKEND=redis
LLM_RPM_BACKEND=redis
LLM_TPM_BACKEND=redis
OPENAI_TPM=200000
# Priority lanes: centropic:analyze:queue:p0|p1|p2 (Business|Plus|Free)
# Optional S3 pack offload (keeps Postgres lean at high volume)
# ANALYZE_ARTIFACT_STORE=s3
# ANALYZE_S3_BUCKET=centropic-analyze-packs  # requires AWS_* creds
# ANALYZE_S3_PREFIX=analyze-packs
# ANALYZE_S3_REGION=eu-central-1
PUBLIC_SITE_URL=https://centropic.ai
PADDLE_ENV=production
SOV_DAILY_BUDGET_CENTS=5000
ALLOW_DROP_ANALYSIS_JOBS=0
MAIL_FROM=Centropic <noreply@centropic.ai>
ADMIN_EMAIL=admin@centropic.ai
```

### Redis (coda analisi + RPM condiviso)

```bash
sudo apt-get install -y redis-server
sudo systemctl enable --now redis-server
```

Senza `REDIS_URL` (o con `ANALYZE_QUEUE_BACKEND=db`) i worker restano sul claim FIFO Postgres.
Con `LLM_TPM_BACKEND=redis` i worker condividono anche il budget token/minuto.
Con `ANALYZE_ARTIFACT_STORE=s3` i pack ottimizzazione vanno su object storage (`pack_uri`); senza bucket resta tutto in Postgres.

### MinIO locale (S3-compatible, loopback)

Se non ci sono credenziali AWS cloud, sul VPS:

```bash
sudo bash scripts/setup_minio_pack_store.sh
systemctl restart aio-bot aio-bot-analyze.service
```

Crea bucket `centropic-analyze-packs`, scrive `AWS_*` + `ANALYZE_S3_*` in `.env`, avvia `aio-bot-minio.service` su `127.0.0.1:9000`.

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
# Long-running loop (preferred)
sudo systemctl enable --now aio-bot-analyze.service
# Optional safety-net oneshot every 10 min
sudo systemctl enable --now aio-bot-analyze.timer
sudo -u aio-bot .venv/bin/python scripts/analyze_worker.py --loop -v
```

After upgrading from the old oneshot-only unit:

```bash
sudo systemctl daemon-reload
sudo systemctl disable --now aio-bot-analyze.timer || true
sudo systemctl enable --now aio-bot-analyze.service
sudo systemctl enable --now aio-bot-analyze.timer   # backup oneshot
```

### Multi-host / più processi worker

Claim esclusivo = Postgres (`lease_token` + `pg_advisory_xact_lock` sul cap globale).
Dispatch = stesso `REDIS_URL`. Ogni host può girare solo il worker (senza Gunicorn).

**Stesso host, N istanze isolate:**

```bash
sudo cp deploy/aio-bot-analyze@.service /etc/systemd/system/
sudo systemctl daemon-reload
# opzionale: concurrency per istanza in /opt/aio-bot/deploy/analyze-worker-1.env
sudo systemctl enable --now aio-bot-analyze@1 aio-bot-analyze@2
# se usi @instance, spegni il service monolitico per non doppiare:
# sudo systemctl disable --now aio-bot-analyze.service
```

**Host dedicato (solo worker):**

```bash
# .env con DATABASE_URL + REDIS_URL uguali al web
sudo cp deploy/aio-bot-analyze-remote.service /etc/systemd/system/aio-bot-analyze.service
sudo systemctl enable --now aio-bot-analyze.service
```

Dimensionare: `DB_POOL_SIZE ≥ WEB_CONCURRENCY×WEB_THREADS + Σ ANALYZE_WORKER_CONCURRENCY`.

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


## FinOps margin levers

```env
USAGE_DEBIT_MODE=aggregate   # one ceil per job (more analyses per MRR)
SOV_PROMPT_MODE=fast
SOV_MAX_TOKENS=200
PROMPT_CACHE_ENABLED=1
LLMS_TXT_RESCAN_CACHE=1
LLM_MODEL_GUARD=1
ANALYZE_S3_RETENTION_DAYS=90
```

Weekly pack cleanup: `systemctl enable --now aio-bot-s3-lifecycle.timer`
