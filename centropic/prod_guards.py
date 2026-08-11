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
    try:
        sov_budget = int(os.getenv("SOV_DAILY_BUDGET_CENTS", "5000") or "5000")
    except ValueError:
        sov_budget = -1

    checks = {
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
