# GeoPulse (geopulse.it)

Sito e SaaS per **AI-Driven Visibility (AIO)** e **Generative Engine Optimization (GEO)**:
registrazione utenti, analisi del dominio, pack artifact e **Edge Signals**
(hosting dinamico `llms.txt` / `robots` / `signals.json` via `/e/<token>` + Worker CDN).

> Nota: in GeoPulse, **GEO ≠ GIS** (Geographic Information System) e **AIO ≠ All-in-One**.
> Sono metriche di citabilità IA / answer engine.

Dominio pubblico: **https://geopulse.it**

## Struttura

```
aio-bot/
├── app.py
├── requirements.txt
├── ROADMAP.md
├── database.db          # creato al primo avvio
├── services/
│   ├── analyzer.py      # scrape, probe, score AIO/GEO
│   ├── artifacts.py     # llms.txt, JSON-LD, meta, robots
│   └── edge_signals.py  # hosting dinamico + snippet Worker/Vercel
├── workers/
│   └── geopulse-signals/  # Cloudflare Worker template
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   └── dashboard.html
└── .env.example
```

## Setup

```bash
cd /home/ubuntu/aio-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Imposta FLASK_SECRET_KEY e (opzionale) OPENAI_API_KEY
python app.py
```

Apri http://127.0.0.1:5000

## Deploy su server

Vedi **[DEPLOY.md](./DEPLOY.md)**.

```bash
./scripts/deploy.sh
# oppure remoto:
REMOTE=root@TUO_IP ./scripts/deploy.sh
```

## Note

- Password hash con Werkzeug
- Sessioni Flask + CSRF (Flask-WTF)
- Database SQLite `database.db` via SQLAlchemy (in Docker: volume `/data`)
- Senza `OPENAI_API_KEY` viene usato un generatore fallback basato sullo scraping
- Produzione: Gunicorn + Docker (+ Nginx opzionale)
