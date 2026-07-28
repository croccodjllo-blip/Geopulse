# GeoPulse — Roadmap GEO/AIO (aggiornata 2026-07-27)

> GEO = Generative Engine Optimization · AIO = AI-Driven Visibility  
> GEO ≠ GIS · AIO ≠ All-in-One

## Shipped — readiness stack
- [x] Score AIO/GEO + rating DDD→AAA + badge Stimato/Misurato
- [x] Probe llms/robots/sitemap/ai/humans + bot policy
- [x] Crawl multi-pagina + thin/dupes/orphan
- [x] Pack ZIP (llms, JSON-LD, meta, robots, checklist)
- [x] Stripe Plus + async jobs + rescan + history/diff
- [x] Onestà metodologica + guide pubbliche

## Shipped — suite avanzata (questo deploy)
### P0
- [x] **Citation monitor** multi-engine (`services/citation_monitor.py`) — OpenAI + Perplexity measured; altri pending
- [x] **Prompt bank** custom (`/dashboard/impostazioni`)
- [x] **Alert outbound** email + webhook HMAC (`services/alerts.py`)
- [x] **Publish verify loop** (`/dashboard/verify/<id>` + in-run findings)

### P1
- [x] **Brand entity graph**
- [x] **Citability audit** (date/stats/quote/claim)
- [x] **Schema quality validator**
- [x] **Competitor snapshot** nel citation monitor + score rivali esistenti
- [x] **Locale / hreflang suite**
- [x] **JS crawl scaffold** (`JS_CRAWL_ENABLED` + Playwright opzionale)

### P2
- [x] **Public API** `POST /api/v1/analyze`, `GET /api/v1/sites` + API key
- [x] **llms.txt / ai.txt semantic lint**
- [x] **Local pack** heuristics (LocalBusiness vs digitale)
- [x] **Agency white-label** MD export
- [x] **GSC scaffold** (`GOOGLE_OAUTH_*`)
- [x] **Edge Signals hosting** (`/e/<token>/*` + Cloudflare Worker template)
- [x] **Platform hardening P0–P2** (SSRF webhook, measured Plus-only, claim atomico, limiter SQLite, Edge rate-limit, test suite)

## Next (connector depth)
- [ ] AI Overview / Claude / Copilot live connectors
- [ ] GSC OAuth complete + Search Analytics overlay
- [ ] CMS push / GitHub PR apply pack
- [ ] Multi-region Edge cache (Cloudflare in front of `/e/`)
- [ ] Postgres managed + backup offsite
- [ ] Playwright default path in crawl BFS
- [ ] PDF white-label branded
- [ ] Alembic versioned migrations (replace ensure_schema DROP)

## Env keys utili
```
OPENAI_API_KEY=
PERPLEXITY_API_KEY=
MEASURED_SOV_ON_ANALYZE=1
JS_CRAWL_ENABLED=0
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
```
