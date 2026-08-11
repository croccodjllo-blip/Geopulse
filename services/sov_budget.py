"""Daily spend guardrail for measured Share-of-Voice probes."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_


SOV_DESCRIPTION_TERMS: tuple[str, ...] = (
    "sov",
    "citation",
    "openai",
    "perplexity",
    "anthropic",
    "gemini",
    "grok",
    "xai",
    "copilot",
    "measured",
)


class SovDailyBudgetExceeded(RuntimeError):
    """The next measured SoV debit would exceed today's configured limit."""


def _daily_budget_cents() -> int:
    # Default €50/day platform guardrail. Set SOV_DAILY_BUDGET_CENTS=0 for unlimited.
    try:
        configured = int(os.getenv("SOV_DAILY_BUDGET_CENTS", "5000") or "5000")
    except (TypeError, ValueError):
        configured = 5000
    return max(0, configured)


def sov_spent_today_cents(
    db_session: Any,
    CreditLedger: Any,
    user_id: int,
) -> int:
    """Sum today's UTC debit rows attributable to SoV/citation engines."""
    start = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    end = start + timedelta(days=1)
    description = func.lower(func.coalesce(CreditLedger.description, ""))
    matches_engine = or_(
        *(description.like(f"%{term}%") for term in SOV_DESCRIPTION_TERMS)
    )
    spent = (
        db_session.query(
            func.coalesce(func.sum(-CreditLedger.amount_cents), 0)
        )
        .filter(
            CreditLedger.user_id == int(user_id),
            CreditLedger.amount_cents < 0,
            CreditLedger.created_at >= start,
            CreditLedger.created_at < end,
            matches_engine,
        )
        .scalar()
    )
    return max(0, int(spent or 0))


def sov_budget_status(user: Any, spent_cents: int) -> dict[str, int | bool]:
    """Return the global daily SoV budget status for one user."""
    del user  # Reserved for future per-user overrides.
    budget_cents = _daily_budget_cents()
    spent = max(0, int(spent_cents or 0))
    unlimited = budget_cents == 0
    return {
        "budget_cents": budget_cents,
        "spent_cents": spent,
        "remaining_cents": 0 if unlimited else max(0, budget_cents - spent),
        "unlimited": unlimited,
    }


def assert_sov_budget_allows(
    user: Any,
    spent_cents: int,
    next_debit_cents: int,
) -> None:
    """Raise when the next positive debit would cross the daily SoV budget."""
    status = sov_budget_status(user, spent_cents)
    debit = max(0, int(next_debit_cents or 0))
    budget = int(status["budget_cents"])
    spent = int(status["spent_cents"])
    if budget > 0 and spent + debit > budget:
        raise SovDailyBudgetExceeded(
            "Budget SoV giornaliero superato: "
            f"{spent} cent già spesi, {debit} cent per il prossimo probe, "
            f"limite {budget} cent."
        )


__all__ = [
    "SOV_DESCRIPTION_TERMS",
    "SovDailyBudgetExceeded",
    "assert_sov_budget_allows",
    "sov_budget_status",
    "sov_spent_today_cents",
]
