"""Usage-based billing for Centropic analysis.

Architecture
============
1. ESTIMATE  — before the user confirms, calculate the expected AI API cost and
               apply a 77% platform spread so the user sees a fair "service price".
2. PREVIEW   — compute expected improvement score (delta AIO/GEO) from a quick
               lightweight pre-scan or from the last known run.
3. CONFIRM   — the frontend asks the user to confirm the shown price + improvement.
4. CHECK     — verify the user has enough credit balance; refuse if not.
5. DEDUCT    — after the analysis completes, consume actual token usage; issue a
               credit ledger entry.
6. TOPUP     — Stripe Checkout can add credit top-ups (prepaid model, no
               subscription required).

Cost constants
==============
All prices in USD (stored as fractions of cent to avoid floating-point drift).
We store and compute in micro-USD (1 µUSD = 0.000001 USD) internally, then
display in EUR cents using a configurable exchange rate (default 0.92 EUR/USD).

API pricing (July 2026 list prices, subject to change via env overrides):
  gpt-4o-mini    input  $0.15 / 1M tokens  →  0.15 µUSD / token
                 output $0.60 / 1M tokens  →  0.60 µUSD / token
  claude-haiku   input  $0.80 / 1M tokens  →  0.80 µUSD / token
                 output $4.00 / 1M tokens  →  4.00 µUSD / token
  sonar (pplx)   input  $1.00 / 1M tokens  →  1.00 µUSD / token
                 output $1.00 / 1M tokens  →  1.00 µUSD / token

Spread: 77% applied on top of raw API cost.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────── price table (µUSD / token) ──────────────────────

_PRICE_TABLE: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o-mini":        {"in": 0.15, "out": 0.60},
    "gpt-4o":             {"in": 2.50, "out": 10.00},
    "gpt-4-turbo":        {"in": 10.00, "out": 30.00},
    "gpt-3.5-turbo":      {"in": 0.50, "out": 1.50},
    # Anthropic
    "claude-haiku-4-5-20251001": {"in": 0.80, "out": 4.00},
    "claude-haiku-3-5-20251001": {"in": 0.80, "out": 4.00},
    "claude-3-5-haiku-20241022": {"in": 0.80, "out": 4.00},
    "claude-3-haiku-20240307":   {"in": 0.25, "out": 1.25},
    "claude-opus-4":             {"in": 15.00, "out": 75.00},
    "claude-sonnet-4":           {"in": 3.00, "out": 15.00},
    # Perplexity
    "sonar":              {"in": 1.00, "out": 1.00},
    "sonar-pro":          {"in": 3.00, "out": 15.00},
    "sonar-reasoning":    {"in": 1.00, "out": 5.00},
}

_DEFAULT_PRICE = {"in": 1.00, "out": 4.00}   # fallback for unknown models

PLATFORM_SPREAD = float(os.getenv("PLATFORM_SPREAD", "0.77"))   # 77%
USD_TO_EUR = float(os.getenv("USD_TO_EUR", "0.92"))

# minimum balance in EUR cents to allow an analysis
MIN_BALANCE_EUR_CENTS: int = 1  # 0.01 € minimum

# ─────────────────────────── token estimators ─────────────────────────────────

def _model_price(model: str) -> dict[str, float]:
    model_lc = (model or "").lower()
    for key, p in _PRICE_TABLE.items():
        if key in model_lc:
            return p
    return _DEFAULT_PRICE


@dataclass
class TokenBudget:
    """Per-call token estimate."""
    model: str
    input_tokens: int
    output_tokens: int

    def cost_usd_micro(self) -> float:
        p = _model_price(self.model)
        return self.input_tokens * p["in"] + self.output_tokens * p["out"]


def _estimate_llms_txt(model: str) -> TokenBudget:
    """generate_llms_txt() in services/artifacts.py — one call per analysis."""
    # ~800 input (prompt + homepage snippet) · up to 1500 output
    return TokenBudget(model=model, input_tokens=800, output_tokens=1500)


def _estimate_openai_sov(model: str, n_prompts: int) -> TokenBudget:
    """_probe_openai() — up to 8 prompts, 350 out each."""
    n = min(n_prompts, 8)
    return TokenBudget(model=model, input_tokens=n * 150, output_tokens=n * 350)


def _estimate_perplexity_sov(model: str, n_prompts: int) -> TokenBudget:
    n = min(n_prompts, 3)
    return TokenBudget(model=model, input_tokens=n * 150, output_tokens=n * 350)


def _estimate_anthropic_sov(model: str, n_prompts: int) -> TokenBudget:
    n = min(n_prompts, 3)
    return TokenBudget(model=model, input_tokens=n * 150, output_tokens=n * 350)


# ─────────────────────────── estimate API ────────────────────────────────────

@dataclass
class CostEstimate:
    """Full cost estimate for one analysis run."""
    raw_cost_usd_micro: float     # bare API cost
    service_cost_usd_micro: float # with spread applied
    service_cost_eur_cents: int   # what the user is charged (integer cents)
    breakdown: list[dict[str, Any]] = field(default_factory=list)
    run_measured: bool = False
    n_prompts: int = 0

    @property
    def service_cost_eur(self) -> float:
        return self.service_cost_eur_cents / 100.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_cost_usd": round(self.raw_cost_usd_micro / 1_000_000, 6),
            "service_cost_usd": round(self.service_cost_usd_micro / 1_000_000, 6),
            "service_cost_eur_cents": self.service_cost_eur_cents,
            "service_cost_eur": round(self.service_cost_eur, 4),
            "spread_pct": round(PLATFORM_SPREAD * 100),
            "run_measured": self.run_measured,
            "n_prompts": self.n_prompts,
            "breakdown": self.breakdown,
        }


def estimate_analysis_cost(
    *,
    openai_model: str,
    anthropic_model: str,
    perplexity_model: str,
    run_measured: bool,
    n_prompts: int = 5,
    has_openai: bool = True,
    has_perplexity: bool = False,
    has_anthropic: bool = False,
) -> CostEstimate:
    """Estimate the total cost of one analysis run (before it runs)."""
    budgets: list[TokenBudget] = []
    breakdown: list[dict[str, Any]] = []

    # 1. llms.txt generation
    if has_openai:
        b = _estimate_llms_txt(openai_model)
        budgets.append(b)
        breakdown.append({
            "item": "Generazione llms.txt",
            "provider": "openai",
            "model": b.model,
            "input_tokens": b.input_tokens,
            "output_tokens": b.output_tokens,
        })

    # 2. Measured SoV probes (only if Plus + keys configured + flag on)
    if run_measured:
        if has_openai:
            b = _estimate_openai_sov(openai_model, n_prompts)
            budgets.append(b)
            breakdown.append({
                "item": f"Citation probe ChatGPT ({n_prompts} prompt)",
                "provider": "openai",
                "model": b.model,
                "input_tokens": b.input_tokens,
                "output_tokens": b.output_tokens,
            })
        if has_perplexity:
            b = _estimate_perplexity_sov(perplexity_model, n_prompts)
            budgets.append(b)
            breakdown.append({
                "item": f"Citation probe Perplexity ({min(n_prompts,3)} prompt)",
                "provider": "perplexity",
                "model": b.model,
                "input_tokens": b.input_tokens,
                "output_tokens": b.output_tokens,
            })
        if has_anthropic:
            b = _estimate_anthropic_sov(anthropic_model, n_prompts)
            budgets.append(b)
            breakdown.append({
                "item": f"Citation probe Claude ({min(n_prompts,3)} prompt)",
                "provider": "anthropic",
                "model": b.model,
                "input_tokens": b.input_tokens,
                "output_tokens": b.output_tokens,
            })

    raw_micro = sum(b.cost_usd_micro() for b in budgets)
    service_micro = raw_micro * (1 + PLATFORM_SPREAD)
    service_eur_cents = max(1, int(service_micro / 1_000_000 * USD_TO_EUR * 100))

    return CostEstimate(
        raw_cost_usd_micro=raw_micro,
        service_cost_usd_micro=service_micro,
        service_cost_eur_cents=service_eur_cents,
        breakdown=breakdown,
        run_measured=run_measured,
        n_prompts=n_prompts,
    )


# ─────────────────────────── improvement preview ────────────────────────────

@dataclass
class ImprovementPreview:
    """Expected improvement estimate shown to the user before they confirm."""
    current_aio: int | None
    current_geo: int | None
    current_rating: str | None
    expected_aio_delta: int       # e.g. +8
    expected_geo_delta: int
    expected_new_rating: str | None
    improvement_label: str
    improvement_detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_aio": self.current_aio,
            "current_geo": self.current_geo,
            "current_rating": self.current_rating,
            "expected_aio_delta": self.expected_aio_delta,
            "expected_geo_delta": self.expected_geo_delta,
            "expected_new_rating": self.expected_new_rating,
            "improvement_label": self.improvement_label,
            "improvement_detail": self.improvement_detail,
        }


_RATING_ORDER = ["DDD", "DD", "D", "C", "B", "A", "AA", "AAA"]


def _next_rating(current: str | None) -> str | None:
    if not current:
        return None
    try:
        idx = _RATING_ORDER.index(current.upper())
        if idx + 1 < len(_RATING_ORDER):
            return _RATING_ORDER[idx + 1]
        return current.upper()
    except ValueError:
        return None


def _improvement_label(aio_delta: int, geo_delta: int) -> tuple[str, str]:
    avg = (aio_delta + geo_delta) / 2
    if avg >= 20:
        return "Significativo", "L'analisi dovrebbe portare miglioramenti importanti sulla visibilità AI."
    if avg >= 10:
        return "Buono", "Attesi miglioramenti chiari su citabilità e machine-readability."
    if avg >= 5:
        return "Moderato", "Attesi piccoli ma concreti guadagni su score AIO/GEO."
    return "Manutenzione", "Il sito è già ben posizionato — l'analisi valida e aggiorna il profilo."


def estimate_improvement(
    *,
    existing_site: Any | None,      # SiteAnalysis ORM object or None
    run_measured: bool,
    crawl_pages: int,
) -> ImprovementPreview:
    """Estimate improvement for the confirmation dialog."""
    current_aio: int | None = None
    current_geo: int | None = None
    current_rating: str | None = None

    if existing_site is not None:
        current_aio = getattr(existing_site, "aio_score", None)
        current_geo = getattr(existing_site, "geo_score", None)
        current_rating = (getattr(existing_site, "rating", None) or {}).get("code")

    # Deltas are heuristic estimates based on context
    # — first-time analysis (no existing data) → larger expected gains
    # — re-analysis → smaller incremental improvement
    if current_aio is None:
        aio_delta = 18
        geo_delta = 22
    else:
        # Regression toward AAA — the room to grow
        room_aio = max(0, 100 - int(current_aio))
        room_geo = max(0, 100 - int(current_geo or 0))
        aio_delta = max(3, min(15, room_aio // 5))
        geo_delta = max(3, min(15, room_geo // 5))

    # Measured SoV adds citation evidence → extra geo delta
    if run_measured:
        geo_delta = min(100, geo_delta + 8)

    # Deeper crawl → more pages found → higher confidence
    if crawl_pages > 50:
        aio_delta = min(100, aio_delta + 3)

    new_rating = _next_rating(current_rating) if current_aio is not None else "C"
    label, detail = _improvement_label(aio_delta, geo_delta)

    return ImprovementPreview(
        current_aio=current_aio,
        current_geo=current_geo,
        current_rating=current_rating,
        expected_aio_delta=aio_delta,
        expected_geo_delta=geo_delta,
        expected_new_rating=new_rating,
        improvement_label=label,
        improvement_detail=detail,
    )


# ─────────────────────────── credit ledger ────────────────────────────────────
# Credit balance is stored on User.credit_balance_cents (INTEGER, EUR cents).
# Negative balance is never allowed; we refuse the analysis instead.
# Every transaction is logged in the `credit_ledger` table.

def get_balance_cents(user: Any) -> int:
    """Return credit balance in EUR cents (0 if column missing)."""
    return int(getattr(user, "credit_balance_cents", 0) or 0)


def has_sufficient_credit(user: Any, cost_estimate: CostEstimate) -> bool:
    """True if user has enough credit for this analysis."""
    return get_balance_cents(user) >= cost_estimate.service_cost_eur_cents


def deduct_credit(
    db_session: Any,
    CreditLedger: Any,
    user: Any,
    *,
    analysis_run_id: int | None,
    cost_eur_cents: int,
    description: str = "Analisi Centropic",
) -> None:
    """Atomically deduct credit and log the transaction."""
    new_balance = get_balance_cents(user) - cost_eur_cents
    if new_balance < 0:
        raise InsufficientCreditError(
            f"Credito insufficiente: {get_balance_cents(user)} cent disponibili, "
            f"{cost_eur_cents} richiesti."
        )
    user.credit_balance_cents = new_balance
    entry = CreditLedger(
        user_id=user.id,
        analysis_run_id=analysis_run_id,
        amount_cents=-cost_eur_cents,
        balance_after_cents=new_balance,
        description=description,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(entry)
    db_session.flush()


def topup_credit(
    db_session: Any,
    CreditLedger: Any,
    user: Any,
    *,
    amount_eur_cents: int,
    description: str = "Ricarica crediti",
    stripe_payment_intent: str | None = None,
) -> None:
    """Add credit to user balance and log the transaction."""
    new_balance = get_balance_cents(user) + amount_eur_cents
    user.credit_balance_cents = new_balance
    entry = CreditLedger(
        user_id=user.id,
        analysis_run_id=None,
        amount_cents=amount_eur_cents,
        balance_after_cents=new_balance,
        description=description,
        stripe_payment_intent=stripe_payment_intent,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(entry)
    db_session.flush()


class InsufficientCreditError(Exception):
    """Raised when a user tries to run an analysis without enough credit."""


# ─────────────────────────── actual token capture ─────────────────────────────

def record_actual_usage(
    db_session: Any,
    UsageEvent: Any,
    *,
    user_id: int,
    analysis_run_id: int | None,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Persist real token usage and return actual cost in EUR cents."""
    p = _model_price(model)
    raw_micro = input_tokens * p["in"] + output_tokens * p["out"]
    service_micro = raw_micro * (1 + PLATFORM_SPREAD)
    eur_cents = service_micro / 1_000_000 * USD_TO_EUR * 100

    event = UsageEvent(
        user_id=user_id,
        analysis_run_id=analysis_run_id,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        raw_cost_usd_micro=int(raw_micro),
        service_cost_eur_cents=round(eur_cents, 4),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    db_session.flush()
    return eur_cents
