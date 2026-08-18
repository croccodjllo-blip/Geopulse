# Centropic architecture

Layered Flask SaaS package under `centropic/`.

## Layers

| Layer | Module | Responsibility |
|---|---|---|
| Config | `centropic.config` | Env-backed constants, DB URI |
| Extensions | `centropic.extensions` | Unbound `db`, `csrf` |
| Tenancy | `centropic.tenancy` | Organization / membership / site ACL |
| Security | `centropic.csp` | Per-request CSP nonces |
| Ops | `centropic.metrics`, `centropic.ops_health` | Counters, timings, job queue snapshot, optional Sentry |
| HTTP | `centropic.views.*` | Domain route catalogs + register hooks |
| Factory | `centropic.factory` | `create_app()` |
| Data plane | `alembic.ini` + `migrations/` | Versioned schema (Postgres-ready) |
| Compat | `app.py` | WSGI entry, models, route handlers (progressive extraction) |

## Schema lifecycle

Alembic è la fonte di verità per lo schema di produzione: ogni modifica persistente richiede una revisione versionata e un `alembic upgrade head` nel deploy. `app.ensure_schema()` resta esclusivamente un bootstrap legacy per SQLite/dev e non è il percorso di migrazione di produzione.

## Score targets

- HTTP layering: factory + domain views
- Data plane: dialect-gated PRAGMA + Alembic
- Multi-tenancy: Organization model + `user_can_access_site`
- Ops: metrics snapshot on `/health` with `X-Ops-Token` (detail); reclaim via `POST /ops/reclaim-jobs` + same header
- Security: CSP nonce (no blanket script unsafe-inline seed)
- Domain: `User.entitlements` / `User.can()` → `services.entitlements`
- Billing: `CreditLedger.payment_idempotency_key` alias + webhook metrics
