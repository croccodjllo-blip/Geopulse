# Centropic architecture

Layered Flask SaaS package under `centropic/`.

## Layers

| Layer | Module | Responsibility |
|---|---|---|
| Config | `centropic.config` | Env-backed constants, DB URI |
| Extensions | `centropic.extensions` | Unbound `db`, `csrf` |
| Tenancy | `centropic.tenancy` | Organization / membership / site ACL |
| Security | `centropic.csp` | Per-request CSP nonces |
| Ops | `centropic.metrics` | Counters, timings, optional Sentry |
| HTTP | `centropic.views.*` | Domain route catalogs + register hooks |
| Factory | `centropic.factory` | `create_app()` |
| Data plane | `alembic.ini` + `migrations/` | Versioned schema (Postgres-ready) |
| Compat | `app.py` | WSGI entry, models, route handlers |

## Score targets

- HTTP layering: factory + domain views
- Data plane: dialect-gated PRAGMA + Alembic
- Multi-tenancy: Organization model + `user_can_access_site`
- Ops: metrics snapshot on `/health?token=`
- Security: CSP nonce (no blanket script unsafe-inline seed)
- Domain: `User.entitlements` / `User.can()` → `services.entitlements`
- Billing: `CreditLedger.payment_idempotency_key` alias + webhook metrics
