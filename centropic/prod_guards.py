"""Fase 0 production readiness guards (env + billing schema)."""

from __future__ import annotations

import os
from typing import Any


CREDIT_LEDGER_PI_INDEX = "uq_credit_ledger_stripe_pi"


def _truthy(raw: str | None, default: str = "0") -> bool:
    return (raw if raw is not None else default).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def prod_guards_enforced() -> bool:
    """Hard-fail /health on env violations when enabled.

    Disabled under pytest and when CENTROPIC_SKIP_PROD_GUARDS=1.
    Default on when FLASK_DEBUG is off.
    """
    if _truthy(os.getenv("CENTROPIC_SKIP_PROD_GUARDS"), "0"):
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    explicit = (os.getenv("HEALTH_REQUIRE_PROD_GUARDS") or "").strip()
    if explicit:
        return _truthy(explicit, "0")
    return not _truthy(os.getenv("FLASK_DEBUG"), "0")


def evaluate_env_guards() -> dict[str, Any]:
    """Return Fase 0 env checklist using the same defaults as the app."""
    async_analyze = _truthy(os.getenv("ASYNC_ANALYZE"), "1")
    admin_bootstrap = _truthy(os.getenv("ADMIN_BOOTSTRAP"), "0")
    allow_drop = _truthy(os.getenv("ALLOW_DROP_ANALYSIS_JOBS"), "0")
    trust_proxy = _truthy(os.getenv("TRUST_PROXY"), "1")
    behind_nginx = _truthy(os.getenv("BEHIND_NGINX"), "0")
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    allow_sqlite = _truthy(os.getenv("ALLOW_SQLITE_PROD"), "0")
    paddle_webhook = (os.getenv("PADDLE_WEBHOOK_SECRET") or "").strip()
    paddle_api = (os.getenv("PADDLE_API_KEY") or "").strip()
    paddle_client = (os.getenv("PADDLE_CLIENT_TOKEN") or "").strip()
    paddle_price_plus = (os.getenv("PADDLE_PRICE_PLUS_MONTHLY") or "").strip()
    health_detail = (os.getenv("HEALTH_DETAIL_TOKEN") or "").strip()
    sentry_dsn = (os.getenv("SENTRY_DSN") or "").strip()
    require_sentry = _truthy(os.getenv("REQUIRE_SENTRY"), "0")
    try:
        sov_budget = int(os.getenv("SOV_DAILY_BUDGET_CENTS", "5000") or "5000")
    except ValueError:
        sov_budget = -1

    db_is_sqlite = database_url.lower().startswith("sqlite")
    checks = {
        "DATABASE_URL": {
            # Prod must not silently fall back to local SQLite under BASE_DIR.
            "ok": bool(database_url),
            "value": "set" if database_url else "missing",
            "required": "set",
        },
        "DATABASE_ENGINE": {
            # Prefer Postgres in prod; ALLOW_SQLITE_PROD=1 for early Plus GTM.
            "ok": (not db_is_sqlite) or allow_sqlite or (not database_url),
            "value": (
                "sqlite+ALLOW"
                if db_is_sqlite and allow_sqlite
                else ("sqlite" if db_is_sqlite else ("postgres/other" if database_url else "unset"))
            ),
            "required": "postgres (or ALLOW_SQLITE_PROD=1)",
        },
        "ASYNC_ANALYZE": {
            "ok": async_analyze,
            "value": "1" if async_analyze else "0",
            "required": "1",
        },
        "ADMIN_BOOTSTRAP": {
            "ok": not admin_bootstrap,
            "value": "1" if admin_bootstrap else "0",
            "required": "0",
        },
        "SOV_DAILY_BUDGET_CENTS": {
            "ok": sov_budget > 0,
            "value": str(sov_budget),
            "required": ">0",
        },
        "ALLOW_DROP_ANALYSIS_JOBS": {
            "ok": not allow_drop,
            "value": "1" if allow_drop else "0",
            "required": "0",
        },
        "TRUST_PROXY_BEHIND_NGINX": {
            # TRUST_PROXY=1 is correct only when Nginx (or equivalent) is the
            # sole public entrypoint and Gunicorn is not internet-reachable.
            "ok": (not trust_proxy) or behind_nginx,
            "value": (
                f"TRUST_PROXY={'1' if trust_proxy else '0'};"
                f"BEHIND_NGINX={'1' if behind_nginx else '0'}"
            ),
            "required": "TRUST_PROXY=0 or BEHIND_NGINX=1",
        },
        "PADDLE_WEBHOOK_SECRET": {
            "ok": bool(paddle_webhook),
            "value": "set" if paddle_webhook else "missing",
            "required": "set",
        },
        "PADDLE_AUTH": {
            "ok": bool(paddle_api or paddle_client),
            "value": (
                "api+client"
                if paddle_api and paddle_client
                else ("api" if paddle_api else ("client" if paddle_client else "missing"))
            ),
            "required": "PADDLE_API_KEY and/or PADDLE_CLIENT_TOKEN",
        },
        "PADDLE_PRICE_PLUS_MONTHLY": {
            # Paddle auth without a Plus catalog price silently disables
            # checkout/overlay (paddle_plus_enabled() == False) or, worse,
            # leaves the amount-assert helpers with no expected price.
            "ok": bool(paddle_price_plus) or not (paddle_api or paddle_client),
            "value": "set" if paddle_price_plus else "missing",
            "required": "set when PADDLE_API_KEY or PADDLE_CLIENT_TOKEN is set",
        },
        "HEALTH_DETAIL_TOKEN": {
            "ok": bool(health_detail),
            "value": "set" if health_detail else "missing",
            "required": "set",
        },
        "SENTRY_DSN": {
            # Soft by default: REQUIRE_SENTRY=1 to hard-fail without DSN.
            "ok": bool(sentry_dsn) or (not require_sentry),
            "value": "set" if sentry_dsn else ("optional" if not require_sentry else "missing"),
            "required": "set when REQUIRE_SENTRY=1",
        },
    }
    failures = [name for name, row in checks.items() if not row["ok"]]
    return {
        "ok": not failures,
        "failures": failures,
        "checks": checks,
    }


def credit_ledger_pi_index_present(engine: Any) -> bool:
    """True when the payment-idempotency unique index exists."""
    from sqlalchemy import text

    dialect = engine.dialect.name
    with engine.connect() as conn:
        if dialect == "sqlite":
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master "
                    f"WHERE type='index' AND name='{CREDIT_LEDGER_PI_INDEX}'"
                )
            ).fetchone()
        else:
            row = conn.execute(
                text(
                    "SELECT 1 FROM pg_indexes "
                    f"WHERE indexname='{CREDIT_LEDGER_PI_INDEX}'"
                )
            ).fetchone()
    return row is not None


def refresh_credit_ledger_index_ok(engine: Any) -> bool:
    """Re-check and return whether the ledger idempotency index is present."""
    try:
        return credit_ledger_pi_index_present(engine)
    except Exception:
        return False
