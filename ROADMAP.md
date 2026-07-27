# GeoPulse (geopulse.it) — Roadmap di progetto

Piattaforma SaaS per **AI-Driven Visibility (AIO)** e **Generative Engine Optimization (GEO)**:
l’utente si registra, inserisce il sito, riceve analisi e ottimizzazioni automatiche (a partire da `llms.txt`), con piano a pagamento.

> GEO qui non è GIS; AIO non è All-in-One.

Stato attuale: **MVP tecnico locale** (auth, scraping, generazione `llms.txt`, SQLite).

---

## Visione prodotto

| Obiettivo | Definizione di “fatto” |
|-----------|------------------------|
| Valore | Un sito migliorato per answer engine / AI crawler in pochi minuti |
| Monetizzazione | Abbonamento Pro (analisi illimitate + ottimizzazioni + export) |
| Retention | Monitoraggio periodico del sito + alert su regressioni AIO/GEO |

---

## Fase 0 — Fondamenta (completata)

- [x] Struttura Flask + SQLAlchemy + SQLite (`database.db`)
- [x] Registrazione / login / logout con password hash (Werkzeug)
- [x] CSRF e sessioni sicure
- [x] Dashboard: input URL → scrape homepage → `llms.txt`
- [x] Integrazione OpenAI + fallback locale
- [x] UI base (Tailwind CDN): login, register, dashboard

**Exit criteria:** un utente può registrarsi, analizzare `example.com` e vedere il file generato.

---

## Fase 1 — Prodotto usable (MVP pubblico)

Obiettivo: prima versione usabile da early adopter, ancora senza billing complesso.

### 1.1 Qualità analisi
- [x] Score AIO / GEO (0–100) con findings strutturati
- [x] Check dedicati: title, meta, JSON-LD, `llms.txt`, robots, canonical, Open Graph, `lang`
- [x] Probe di `/llms.txt`, `/robots.txt`, `/sitemap.xml`
- [ ] Storico analisi confrontabile (before/after)

### 1.2 Output ottimizzazione
- [x] Pack scaricabili: `llms.txt`, JSON-LD, meta pack, suggerimenti `robots.txt`
- [ ] Preview side-by-side (prima / dopo)
- [x] Download ZIP (+ report.json)

### 1.3 UX account
- [ ] Verifica email (magic link o token)
- [ ] Reset password
- [ ] Profilo utente (nome, lingua, timezone)
- [ ] Limite Free: 1 sito / N analisi al giorno

### 1.4 Affidabilità
- [ ] Code splitting modulare (`models.py`, `auth.py`, `services/analyzer.py`, `services/llm.py`)
- [ ] Logging strutturato + gestione errori utente chiara
- [ ] Test automatici (pytest): auth, analyze, limiti piano
- [ ] `.env` obbligatorio in prod + `FLASK_DEBUG=0`

**Exit criteria:** onboarding in &lt; 3 minuti; output utile anche senza intervento umano.

---

## Fase 2 — Monetizzazione e multi-sito

Obiettivo: SaaS a pagamento.

### 2.1 Billing
- [ ] Stripe Checkout (subscription) + Customer Portal
- [ ] Piani: **Free** / **Pro** (/ **Agency** opzionale)
- [ ] Webhook Stripe → aggiornamento `plan` su `users`
- [ ] Gate: ottimizzazione automatica e multi-sito solo su Pro

### 2.2 Modello dati siti
- [ ] Entità `Site` (URL, dominio, piano, stato)
- [ ] Entità `AnalysisRun` e `OptimizationArtifact`
- [ ] Soft-delete e audit trail

### 2.3 Quote e limiti
- [ ] Free: 1 sito, analisi base
- [ ] Pro: fino a N siti, re-scan schedulato, export illimitati
- [ ] Rate limit per IP/utente sulle API di analisi

**Exit criteria:** un utente paga, sblocca Pro, ottimizza più siti.

---

## Fase 3 — Automazione “sempre attiva”

Obiettivo: il software ottimizza in continuo, non solo on-demand.

### 3.1 Worker / code
- [ ] Coda job (RQ/Celery + Redis, oppure APScheduler per MVP)
- [ ] Job: `analyze_site`, `generate_artifacts`, `weekly_rescan`
- [ ] Stato job in dashboard (queued / running / done / error)

### 3.2 Monitoraggio
- [ ] Cron giornaliero/settimanale per siti Pro
- [ ] Alert email/Telegram se lo score cala o `llms.txt` sparisce
- [ ] Healthcheck endpoint (`/health`)

### 3.3 Consegna ottimizzazioni
- [ ] Opzione A: artifact da copiare (attuale, esteso)
- [ ] Opzione B: integrazione CMS (WordPress plugin / webhook)
- [ ] Opzione C: PR automatica su repo GitHub del cliente (avanzato)

**Exit criteria:** il cliente “set & forget”: riceve aggiornamenti senza tornare ogni giorno.

---

## Fase 4 — Motore GEO/AIO avanzato

Obiettivo: differenziazione competitiva.

- [ ] Knowledge graph del brand (entità, offering, FAQ)
- [ ] Generazione FAQ / Q&A schema per query tipiche AI
- [ ] Supporto multilingua (IT/EN/ES) degli artifact
- [ ] Benchmark vs competitor URL
- [ ] Report PDF white-label (piano Agency)
- [ ] API pubblica autenticata (API key) per agenzie

**Exit criteria:** report e artifact percepiti come “specialistici”, non generici.

---

## Fase 5 — Produzione e crescita

### 5.1 Deploy
- [x] Docker + docker-compose (app Gunicorn + volume SQLite)
- [ ] Migrazione SQLite → PostgreSQL
- [x] Reverse proxy Nginx (compose profile / host config)
- [ ] HTTPS Certbot in produzione
- [ ] Backup DB automatici

### 5.2 Osservabilità e sicurezza
- [ ] Sentry (errori) + metriche base
- [ ] Audit login / brute-force protection
- [x] Policy privacy + termini + cookie banner se necessario
- [x] `/ai.txt` + schema FAQPage / SoftwareApplication
- [x] Copy honesty: score/SoV come probe/euristici (non “misurati” di default)
- [x] SSRF guard su crawl/probe + redirect hop check
- [x] Admin senza password default / senza reset a ogni boot
- [x] SoV da robots probe persistito (non artifact pack)
- [x] Evidence badge Misurato/Stimato sui findings
- [x] Backup SQLite giornaliero (systemd timer)
- [ ] Hardening: secrets, CSRF, headers di sicurezza

### 5.3 Go-to-market
- [ ] Landing marketing (value prop GEO/AIO chiara)
- [ ] Onboarding guided tour
- [ ] Contenuti SEO: guide `llms.txt`, JSON-LD, GEO
- [ ] Referral / affiliazione per agenzie

**Exit criteria:** ambiente stabile in produzione, primi clienti paganti ricorrenti.

---

## Backlog prioritizzato (ordine consigliato)

1. Modularizzare `app.py` + test pytest  
2. Score AIO/GEO + findings  
3. Download pack ottimizzazioni  
4. Stripe Pro  
5. Multi-sito + storico run  
6. Job periodici di re-scan  
7. Postgres + Docker deploy  
8. Integrazioni CMS / GitHub  

---

## Stack target (evoluzione)

| Area | Oggi | Target |
|------|------|--------|
| Backend | Flask monolitico | Flask modular / blueprints |
| DB | SQLite | PostgreSQL |
| AI | OpenAI chat | OpenAI + prompt versionati |
| Jobs | sincroni nella request | Redis + worker |
| Billing | — | Stripe Billing |
| Front | Jinja + Tailwind CDN | Jinja (o HTMX) + design system |

---

## Metriche di successo

| Metrica | Target early |
|---------|--------------|
| Time-to-first-llms.txt | &lt; 60 secondi |
| Attivazione (registrato → prima analisi) | &gt; 60% |
| Conversion Free → Pro | &gt; 5% |
| Error rate analisi | &lt; 5% |
| NPS early adopter | &gt; 30 |

---

## Prossimo incremento consigliato

**Completato:** score AIO/GEO, findings, pack artifact + ZIP.

**Sprint successivo:** Fase 1.3 (reset password / limiti Free) oppure direttamente **Stripe Pro (Fase 2)**.
