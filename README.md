# Centropic (`centropic.ai`)

SaaS B2B per **AI-Driven Visibility (AIO)** e **Generative Engine Optimization (GEO)**:
registrazione, diagnosi dominio, pack artifact e **Edge Signals**
(hosting dinamico `llms.txt` / `robots` / `signals.json` via `/e/<token>`).

> **GEO ≠ GIS** · **AIO ≠ All-in-One** — metriche di citabilità nelle risposte IA.
> Ex-brand GeoPulse resta solo come continuità SEO (`alternateName`) e alias legacy API (`gp_`, `X-GeoPulse-*`).

Dominio pubblico: **https://centropic.ai**

## Struttura

```
aio-bot/
├── app.py                 # HTTP surface (migrazione progressiva → centropic/views)
├── centropic/             # factory, tenancy, CSP, metrics, view catalogs
├── services/              # analyzer, billing, jobs, entitlements, edge…
├── migrations/            # Alembic (source of truth in produzione)
├── workers/               # Edge / signals worker templates
├── templates/             # Jinja (marketing + dashboard)
├── static/                # CSS/JS + geo-ui React build
├── tests/
├── ROADMAP.md
└── DEPLOY.md
```

## Setup locale

```bash
cd /home/ubuntu/aio-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Imposta FLASK_SECRET_KEY e (opzionale) chiavi LLM / Paddle
python app.py
```

Apri http://127.0.0.1:5000

## Deploy

Vedi **[DEPLOY.md](./DEPLOY.md)**. Produzione: Gunicorn + git push VPS; schema via **Alembic** (`alembic upgrade head`).

```bash
./scripts/deploy.sh
# oppure:
REMOTE=root@TUO_IP ./scripts/deploy.sh
```

## Note

- Sessioni Flask + CSRF (Flask-WTF); `session_version` invalida sessioni dopo reset password
- API pubblica: Bearer `ct_…` (legacy `gp_…` ancora accettato)
- Edge / webhook: header `X-Centropic-*` (+ alias `X-GeoPulse-*`)
- Piani: Free / Plus / Business — source of truth `services/entitlements.py`
- Test: `python3 -m pytest -q`
