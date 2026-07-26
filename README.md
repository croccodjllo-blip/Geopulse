# AIO-Bot

SaaS iniziale per **GEO/AIO Optimization**: registrazione utenti, analisi homepage e generazione automatica di `llms.txt` (OpenAI + fallback locale).

## Struttura

```
aio-bot/
├── app.py
├── requirements.txt
├── ROADMAP.md
├── database.db          # creato al primo avvio
├── services/
│   ├── analyzer.py      # scrape, probe, score AIO/GEO
│   └── artifacts.py     # llms.txt, JSON-LD, meta, robots
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

## Note

- Password hash con Werkzeug
- Sessioni Flask + CSRF (Flask-WTF)
- Database SQLite `database.db` via SQLAlchemy
- Senza `OPENAI_API_KEY` viene usato un generatore fallback basato sullo scraping
