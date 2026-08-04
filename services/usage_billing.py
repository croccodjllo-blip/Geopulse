"""Usage-based billing for Centropic analysis.

Architecture
============
1. ESTIMATE  — before the user confirms, calculate the expected AI API cost and
               apply a 77% platform spread so the user sees a fair "service price".
2. PREVIEW   — show baseline AIO/GEO (if any) and honest diagnosis / re-measure copy.
3. CONFIRM   — the frontend asks the user to confirm the shown price + re-measure copy.
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
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy import case, text

from services.ssrf import UnsafeURLError, safe_get
from services.token_units import format_token_amount

logger = logging.getLogger(__name__)


class JobLeaseLostError(RuntimeError):
    """Worker lost the analyze job lease — stop LLM calls and billing."""


class InsufficientCreditError(Exception):
    """Raised when a user tries to run an analysis without enough credit."""


class ConcurrentAnalysisError(Exception):
    """Raised when the user already has too many pending/running jobs."""


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
    # Google Gemini (approx. Flash list prices)
    "gemini-2.0-flash":       {"in": 0.10, "out": 0.40},
    "gemini-2.0-flash-lite":  {"in": 0.075, "out": 0.30},
    "gemini-1.5-flash":       {"in": 0.075, "out": 0.30},
    "gemini-2.5-flash":       {"in": 0.15, "out": 0.60},
    "gemini-flash-latest":    {"in": 0.10, "out": 0.40},
    # xAI Grok (approx. list prices)
    "grok-4-1-fast-non-reasoning": {"in": 0.20, "out": 0.50},
    "grok-4-1-fast":               {"in": 0.20, "out": 0.50},
    "grok-3-mini":                 {"in": 0.30, "out": 0.50},
    "grok-3":                      {"in": 3.00, "out": 15.00},
    "grok-4.5":                    {"in": 2.00, "out": 6.00},
}

_DEFAULT_PRICE = {"in": 1.00, "out": 4.00}   # fallback for unknown models

PLATFORM_SPREAD = float(os.getenv("PLATFORM_SPREAD", "0.77"))   # 77%
USD_TO_EUR = float(os.getenv("USD_TO_EUR", "0.92"))
MAX_TOKENS_PER_CALL = int(os.getenv("MAX_TOKENS_PER_CALL", "1500"))
MAX_PREFLIGHT_WORDS = int(os.getenv("MAX_PREFLIGHT_WORDS", "12000"))
# Extra margin required before starting analysis to reduce mid-run credit stops.
GRACE_MARGIN = min(0.50, max(0.0, float(os.getenv("CREDIT_GRACE_MARGIN", "0.08"))))

# minimum balance in EUR cents to allow an analysis
MIN_BALANCE_EUR_CENTS: int = 1  # 0.01 € minimum

# ─────────────────────────── token estimators ─────────────────────────────────

def _model_price(model: str) -> dict[str, float]:
    """Resolve model pricing. Prefer exact match, then longest substring key.

    Order matters: ``sonar`` must not win over ``sonar-pro``.
    """
    model_lc = (model or "").lower().strip()
    if not model_lc:
        return _DEFAULT_PRICE
    if model_lc in _PRICE_TABLE:
        return _PRICE_TABLE[model_lc]
    for key in sorted(_PRICE_TABLE.keys(), key=len, reverse=True):
        if key in model_lc:
            return _PRICE_TABLE[key]
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


def _estimate_sov_call(model: str) -> TokenBudget:
    """One citation-monitor prompt call (matches runtime per-prompt debit)."""
    return TokenBudget(model=model, input_tokens=150, output_tokens=350)


def _openai_sov_calls(n_prompts: int) -> int:
    # citation_monitor._probe_openai iterates all prompts (cap kept for sanity).
    return max(0, min(int(n_prompts or 0), 8))


def _other_sov_calls(n_prompts: int) -> int:
    # Non-OpenAI probes use prompts[:3].
    return max(0, min(int(n_prompts or 0), 3))


def _service_eur_cents_from_micro(raw_micro: float) -> float:
    """Fractional EUR cents after platform spread (pre-ceil)."""
    service_micro = float(raw_micro) * (1 + PLATFORM_SPREAD)
    return service_micro / 1_000_000 * USD_TO_EUR * 100


def _debit_cents_for_budget(budget: TokenBudget) -> int:
    """Mirror runtime ``debit_cents_from_usage`` for a single AI call."""
    return debit_cents_from_usage(_service_eur_cents_from_micro(budget.cost_usd_micro()))


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
    estimated_calls: int = 0

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
            "estimated_calls": self.estimated_calls,
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
    gemini_model: str = "gemini-flash-latest",
    has_gemini: bool = False,
    xai_model: str = "grok-4-1-fast-non-reasoning",
    has_xai: bool = False,
    azure_model: str = "gpt-4o-mini",
    has_azure: bool = False,
) -> CostEstimate:
    """Estimate total analysis cost mirroring realtime per-call ceil billing.

    Runtime debits each AI HTTP call separately with ``ceil`` to whole EUR
    cents. Aggregating tokens then rounding once under-estimates measured
    multi-prompt runs; this estimate expands one budget per expected call.
    """
    call_budgets: list[TokenBudget] = []
    breakdown: list[dict[str, Any]] = []

    def _add_group(
        *,
        item: str,
        provider: str,
        model: str,
        calls: int,
        per_call: TokenBudget,
    ) -> None:
        if calls <= 0:
            return
        debit = 0
        raw = 0.0
        for _ in range(calls):
            call_budgets.append(per_call)
            debit += _debit_cents_for_budget(per_call)
            raw += per_call.cost_usd_micro()
        breakdown.append({
            "item": item,
            "provider": provider,
            "model": model,
            "input_tokens": per_call.input_tokens * calls,
            "output_tokens": per_call.output_tokens * calls,
            "estimated_calls": calls,
            "estimated_debit_cents": debit,
        })

    # 1. llms.txt generation — one OpenAI call
    if has_openai:
        b = _estimate_llms_txt(openai_model)
        _add_group(
            item="Generazione llms.txt",
            provider="openai",
            model=b.model,
            calls=1,
            per_call=b,
        )

    # 2. Measured SoV probes — one debit per prompt call (matches citation_monitor)
    if run_measured:
        if has_openai:
            n = _openai_sov_calls(n_prompts)
            _add_group(
                item=f"Citation probe ChatGPT ({n} call)",
                provider="openai",
                model=openai_model,
                calls=n,
                per_call=_estimate_sov_call(openai_model),
            )
        if has_perplexity:
            n = _other_sov_calls(n_prompts)
            _add_group(
                item=f"Citation probe Perplexity ({n} call)",
                provider="perplexity",
                model=perplexity_model,
                calls=n,
                per_call=_estimate_sov_call(perplexity_model),
            )
        if has_anthropic:
            n = _other_sov_calls(n_prompts)
            _add_group(
                item=f"Citation probe Claude ({n} call)",
                provider="anthropic",
                model=anthropic_model,
                calls=n,
                per_call=_estimate_sov_call(anthropic_model),
            )
        if has_gemini:
            n = _other_sov_calls(n_prompts)
            _add_group(
                item=f"Citation probe Gemini ({n} call)",
                provider="google",
                model=gemini_model,
                calls=n,
                per_call=_estimate_sov_call(gemini_model),
            )
        if has_xai:
            n = _other_sov_calls(n_prompts)
            _add_group(
                item=f"Citation probe Grok ({n} call)",
                provider="xai",
                model=xai_model,
                calls=n,
                per_call=_estimate_sov_call(xai_model),
            )
        if has_azure:
            n = _other_sov_calls(n_prompts)
            _add_group(
                item=f"Citation probe Copilot/Azure ({n} call)",
                provider="azure",
                model=azure_model,
                calls=n,
                per_call=_estimate_sov_call(azure_model),
            )

    raw_micro = sum(b.cost_usd_micro() for b in call_budgets)
    service_micro = raw_micro * (1 + PLATFORM_SPREAD)
    # Sum of per-call ceils (= what ledger will charge), never below 1¢ if any work.
    service_eur_cents = sum(_debit_cents_for_budget(b) for b in call_budgets)
    if call_budgets and service_eur_cents < 1:
        service_eur_cents = 1

    return CostEstimate(
        raw_cost_usd_micro=raw_micro,
        service_cost_usd_micro=service_micro,
        service_cost_eur_cents=service_eur_cents,
        breakdown=breakdown,
        run_measured=run_measured,
        n_prompts=n_prompts,
        estimated_calls=len(call_budgets),
    )


@dataclass
class PageWordCountCheck:
    word_count: int
    is_giant: bool
    required_cost_cents: int
    message: str


def preflight_word_count(url: str, *, timeout_seconds: float = 20.0) -> int:
    """Fetch public page HTML and count visible words before AI calls."""
    sess = requests.Session()
    resp = safe_get(sess, url, timeout=timeout_seconds, max_redirects=3)
    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "text/html" not in content_type and "text/" not in content_type:
        return 0
    html = resp.text or ""
    # Remove script/style and rough tags; then count token-like words.
    html = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", html)
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    words = re.findall(r"[A-Za-z0-9À-ÿ][A-Za-z0-9À-ÿ'’_-]*", text)
    return len(words)


def giant_page_required_cost_cents(base_cost_cents: int, word_count: int) -> int:
    """Scale required credit for very large pages; used as upfront guardrail."""
    if word_count <= MAX_PREFLIGHT_WORDS:
        return max(1, int(base_cost_cents))
    # Linear overage multiplier with hard cap to avoid pathological estimates.
    over = word_count - MAX_PREFLIGHT_WORDS
    ratio = over / max(1, MAX_PREFLIGHT_WORDS)
    multiplier = min(4.0, 1.0 + ratio)
    return max(1, int(base_cost_cents * multiplier))


def check_page_word_budget(
    *,
    url: str,
    base_cost_cents: int,
    balance_cents: int,
    unlimited: bool = False,
) -> PageWordCountCheck:
    """
    Preventive guard:
    if page is giant, block before AI and tell user required credit.
    Admin/unlimited users bypass the giant-page block entirely.
    """
    if unlimited:
        return PageWordCountCheck(
            word_count=0,
            is_giant=False,
            required_cost_cents=max(1, int(base_cost_cents)),
            message="",
        )
    try:
        words = preflight_word_count(url)
    except (requests.RequestException, UnsafeURLError):
        # If preflight fails due network/SSRF checks, do not hide the main flow.
        return PageWordCountCheck(
            word_count=0,
            is_giant=False,
            required_cost_cents=max(1, int(base_cost_cents)),
            message="",
        )
    required = giant_page_required_cost_cents(base_cost_cents, words)
    if words > MAX_PREFLIGHT_WORDS:
        shortage = max(0, required - balance_cents)
        # Hard-block only when credit is insufficient for the scaled cost.
        if shortage > 0:
            msg = (
                f"Pagina molto grande ({words} parole). "
                f"Token richiesti stimati: {format_token_amount(required)}. "
                f"Ti mancano {format_token_amount(shortage)}."
            )
            return PageWordCountCheck(
                word_count=words,
                is_giant=True,
                required_cost_cents=required,
                message=msg,
            )
        return PageWordCountCheck(
            word_count=words,
            is_giant=False,
            required_cost_cents=required,
            message=(
                f"Pagina grande ({words} parole): costo scalato a "
                f"{format_token_amount(required)}."
            ),
        )
    return PageWordCountCheck(
        word_count=words,
        is_giant=False,
        required_cost_cents=required,
        message="",
    )


# ─────────────────────────── improvement preview ────────────────────────────

@dataclass
class ImprovementPreview:
    """Baseline + re-measure copy shown before the user confirms an analysis."""
    current_aio: int | None
    current_geo: int | None
    current_rating: str | None
    improvement_label: str
    improvement_detail: str


def _refresh_label(
    *,
    has_baseline: bool,
    run_measured: bool,
    crawl_pages: int,
) -> tuple[str, str]:
    """Honest confirm copy — re-measure signals, do not sell score uplift."""
    depth = f"Crawl fino a {int(crawl_pages)} pagine. " if crawl_pages else ""
    measured = (
        "Include probe SoV Misurato (Plus). "
        if run_measured
        else ""
    )
    if not has_baseline:
        return (
            "Prima diagnosi",
            depth
            + measured
            + "Misura i segnali pubblici attuali e produce score AIO/GEO, findings e pack. "
            "Non prevede un guadagno di score: il risultato dipende dal sito.",
        )
    return (
        "Ri-misurazione",
        depth
        + measured
        + "Ricalcola score e findings dopo eventuali fix pubblicati. "
        "Gli score possono salire o scendere — non è un miglioramento garantito.",
    )


def estimate_improvement(
    *,
    existing_site: Any | None,      # SiteAnalysis ORM object or None
    run_measured: bool,
    crawl_pages: int,
) -> ImprovementPreview:
    """Baseline + re-measure preview for the confirmation dialog (no fake uplift)."""
    current_aio: int | None = None
    current_geo: int | None = None
    current_rating: str | None = None

    if existing_site is not None:
        current_aio = getattr(existing_site, "aio_score", None)
        current_geo = getattr(existing_site, "geo_score", None)
        current_rating = (getattr(existing_site, "rating", None) or {}).get("code")

    label, detail = _refresh_label(
        has_baseline=current_aio is not None,
        run_measured=run_measured,
        crawl_pages=crawl_pages,
    )

    return ImprovementPreview(
        current_aio=current_aio,
        current_geo=current_geo,
        current_rating=current_rating,
        improvement_label=label,
        improvement_detail=detail,
    )


# ─────────────────────────── credit ledger ────────────────────────────────────
# Credit balance is stored on User.credit_balance_cents (INTEGER, EUR cents).
# Negative balance is never allowed; we refuse the analysis instead.
# Every transaction is logged in the `credit_ledger` table.

def is_unlimited_user(user: Any) -> bool:
    """Admin and internal users have unlimited credit — never billed.

    Aligns with ``User.is_admin`` (plan or role) plus explicit ``internal``.
    """
    if bool(getattr(user, "is_admin", False)):
        return True
    plan = (getattr(user, "plan", None) or "").lower()
    if plan == "admin":
        return True
    role = (getattr(user, "role", None) or "").lower()
    return role in {"admin", "internal"}


def debit_cents_from_usage(charged_eur_cents: float) -> int:
    """Convert fractional EUR cents from a single AI call into ledger cents.

    Ceil to avoid under-billing; return 0 when usage cost is empty.
    """
    if charged_eur_cents <= 0:
        return 0
    return int(math.ceil(charged_eur_cents - 1e-12))


def get_held_cents(user: Any) -> int:
    return max(0, int(getattr(user, "credit_held_cents", 0) or 0))


def get_balance_cents(user: Any) -> int:
    """Spendable credit in EUR cents (balance minus active holds).

    Admin/unlimited users return a very large sentinel value.
    """
    if is_unlimited_user(user):
        return 2_147_483_647  # effectively infinite
    raw = int(getattr(user, "credit_balance_cents", 0) or 0)
    return max(0, raw - get_held_cents(user))


def has_sufficient_credit(user: Any, cost_estimate: CostEstimate) -> bool:
    """True if user has enough credit for this analysis.
    Admin/unlimited users always pass this check."""
    if is_unlimited_user(user):
        return True
    required = required_credit_with_grace_cents(cost_estimate.service_cost_eur_cents)
    return get_balance_cents(user) >= required


def has_sufficient_credit_for_job(
    user: Any,
    cost_estimate: CostEstimate,
    *,
    reserved_cents: int = 0,
) -> bool:
    """Like ``has_sufficient_credit`` but counts this job's hold as available.

    Worker preflight must not treat the job's own ``held_cents`` as unavailable,
    or it falsely fails and releases the hold.
    """
    if is_unlimited_user(user):
        return True
    required = required_credit_with_grace_cents(cost_estimate.service_cost_eur_cents)
    available = get_balance_cents(user) + max(0, int(reserved_cents or 0))
    return available >= required


def required_credit_with_grace_cents(base_cost_cents: int) -> int:
    """Upfront required credit with safety margin to avoid mid-analysis stops."""
    return max(MIN_BALANCE_EUR_CENTS, int(math.ceil(max(1, base_cost_cents) * (1 + GRACE_MARGIN))))


def debit_leased_job_usage(
    db_session: Any,
    CreditLedger: Any,
    AnalysisJob: Any,
    user: Any,
    job: Any,
    *,
    lease_token: str,
    cost_eur_cents: int,
    description: str,
) -> int:
    """Atomically verify job lease ownership then deduct credit (H1).

    Takes a reserved write lock (SQLite BEGIN IMMEDIATE) and ``FOR UPDATE`` on
    the job row so a reclaim cannot race between the lease check and the debit.
    Updates ``job.held_cents`` / ``job.billed_cents`` in the same transaction.

    Returns cents actually debited (0 for unlimited users or non-positive cost).
    Raises ``JobLeaseLostError`` if the lease was lost.
    """
    if cost_eur_cents <= 0:
        return 0
    try:
        _begin_immediate(db_session)
    except Exception:
        pass
    locked = (
        db_session.query(AnalysisJob)
        .filter(AnalysisJob.id == job.id)
        .with_for_update()
        .first()
    )
    if (
        locked is None
        or getattr(locked, "status", None) != "running"
        or getattr(locked, "lease_token", None) != lease_token
    ):
        raise JobLeaseLostError("job lease lost — stop billing")

    held_now = int(getattr(locked, "held_cents", 0) or 0)
    deduct_credit(
        db_session,
        CreditLedger,
        user,
        analysis_run_id=None,
        cost_eur_cents=cost_eur_cents,
        description=description,
        reserved_cents=held_now,
    )
    if held_now > 0 and not is_unlimited_user(user):
        consumed = consume_hold(
            db_session, user, amount_cents=min(cost_eur_cents, held_now)
        )
        locked.held_cents = max(0, held_now - int(consumed or 0))
        job.held_cents = locked.held_cents
    locked.billed_cents = int(getattr(locked, "billed_cents", 0) or 0) + cost_eur_cents
    job.billed_cents = locked.billed_cents
    db_session.flush()
    return cost_eur_cents


def deduct_credit(
    db_session: Any,
    CreditLedger: Any,
    user: Any,
    *,
    analysis_run_id: int | None,
    cost_eur_cents: int,
    description: str = "Analisi Centropic",
    reserved_cents: int = 0,
) -> None:
    """Atomically deduct credit and log the transaction.

    Uses a conditional UPDATE so concurrent workers cannot drive the balance
    negative even if they both passed a prior Python-level balance check.

    ``reserved_cents`` is hold already reserved for this debit (typically the
    job's remaining ``held_cents``). The update refuses to spend below other
    jobs' holds: ``balance - cost >= max(0, held - reserved)``.

    Admin/unlimited users are never charged — call is silently skipped.
    """
    if is_unlimited_user(user):
        logger.debug("deduct_credit: admin user %s — skip deduction.", getattr(user, "email", "?"))
        return
    if cost_eur_cents <= 0:
        return
    UserModel = type(user)
    reserved = max(0, int(reserved_cents or 0))
    filters = [
        UserModel.id == user.id,
        UserModel.credit_balance_cents >= cost_eur_cents,
    ]
    # Protect other jobs' holds when the model tracks credit_held_cents.
    if hasattr(UserModel, "credit_held_cents"):
        held_protected = case(
            (
                UserModel.credit_held_cents > reserved,
                UserModel.credit_held_cents - reserved,
            ),
            else_=0,
        )
        filters.append(
            (UserModel.credit_balance_cents - cost_eur_cents) >= held_protected
        )
    updated = (
        db_session.query(UserModel)
        .filter(*filters)
        .update(
            {
                UserModel.credit_balance_cents: UserModel.credit_balance_cents
                - cost_eur_cents
            },
            synchronize_session=False,
        )
    )
    if updated != 1:
        # Refresh for accurate error message
        db_session.refresh(user)
        raise InsufficientCreditError(
            f"Token insufficienti: {format_token_amount(get_balance_cents(user))} disponibili, "
            f"{format_token_amount(cost_eur_cents)} richiesti."
        )
    db_session.refresh(user)
    new_balance = int(user.credit_balance_cents or 0)
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


def _begin_immediate(db_session: Any) -> None:
    """Take a reserved write lock early (critical on SQLite under concurrency)."""
    bind = db_session.get_bind()
    dialect = getattr(getattr(bind, "dialect", None), "name", "") or ""
    if dialect == "sqlite":
        db_session.execute(text("BEGIN IMMEDIATE"))


def assert_can_start_analysis(
    db_session: Any,
    user: Any,
    *,
    AnalysisJob: Any | None = None,
    required_cents: int,
    max_concurrent_jobs: int = 2,
) -> None:
    """Serialize billing decision: lock user row, re-check credit + job concurrency.

    Raises InsufficientCreditError or ConcurrentAnalysisError.
    """
    if is_unlimited_user(user):
        return
    UserModel = type(user)
    try:
        _begin_immediate(db_session)
    except Exception:
        # Non-SQLite / already in a transaction: fall through to FOR UPDATE.
        pass
    locked = (
        db_session.query(UserModel)
        .filter(UserModel.id == user.id)
        .with_for_update()
        .first()
    )
    if locked is None:
        raise InsufficientCreditError("Utente non trovato.")
    # Keep caller's user object in sync with locked row.
    if locked is not user:
        user.credit_balance_cents = locked.credit_balance_cents
        if hasattr(locked, "credit_held_cents"):
            user.credit_held_cents = locked.credit_held_cents
    if AnalysisJob is not None and max_concurrent_jobs > 0:
        active = (
            AnalysisJob.query.filter(
                AnalysisJob.user_id == user.id,
                AnalysisJob.status.in_(("pending", "running")),
            ).count()
        )
        if active >= max_concurrent_jobs:
            raise ConcurrentAnalysisError(
                f"Hai già {active} analisi in coda/esecuzione. "
                "Attendi il completamento prima di avviarne un'altra."
            )
    need = max(1, int(required_cents))
    if get_balance_cents(user) < need:
        raise InsufficientCreditError(
            f"Token insufficienti: {format_token_amount(get_balance_cents(user))} disponibili, "
            f"{format_token_amount(need)} richiesti."
        )


def hold_credit(
    db_session: Any,
    CreditLedger: Any,
    user: Any,
    *,
    amount_cents: int,
    job_id: int | None = None,
    description: str = "Riserva analisi",
) -> int:
    """Atomically reserve spendable credit (balance − held ≥ amount).

    Uses a conditional UPDATE so concurrent holds cannot over-reserve.
    Returns the held amount (0 for unlimited users).
    """
    if is_unlimited_user(user) or amount_cents <= 0:
        return 0
    amount = int(amount_cents)
    UserModel = type(user)
    updated = (
        db_session.query(UserModel)
        .filter(
            UserModel.id == user.id,
            (UserModel.credit_balance_cents - UserModel.credit_held_cents) >= amount,
        )
        .update(
            {
                UserModel.credit_held_cents: UserModel.credit_held_cents + amount
            },
            synchronize_session=False,
        )
    )
    if updated != 1:
        db_session.refresh(user)
        spendable = get_balance_cents(user)
        raise InsufficientCreditError(
            f"Token insufficienti per la riserva: {format_token_amount(spendable)} "
            f"disponibili, {format_token_amount(amount)} richiesti."
        )
    db_session.refresh(user)
    entry = CreditLedger(
        user_id=user.id,
        analysis_run_id=None,
        amount_cents=0,
        balance_after_cents=get_balance_cents(user),
        description=f"{description}" + (f" job#{job_id}" if job_id else ""),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(entry)
    db_session.flush()
    return amount


def release_hold(
    db_session: Any,
    user: Any,
    *,
    amount_cents: int,
) -> int:
    """Release remaining job hold back to spendable balance.

    On concurrent race (held already reduced), returns 0 without touching
    other jobs' holds — never clamps the user's entire held balance to 0.
    """
    if is_unlimited_user(user) or amount_cents <= 0:
        return 0
    amount = min(int(amount_cents), get_held_cents(user))
    if amount <= 0:
        return 0
    UserModel = type(user)
    updated = (
        db_session.query(UserModel)
        .filter(
            UserModel.id == user.id,
            UserModel.credit_held_cents >= amount,
        )
        .update(
            {UserModel.credit_held_cents: UserModel.credit_held_cents - amount},
            synchronize_session=False,
        )
    )
    if updated != 1:
        db_session.refresh(user)
        return 0
    db_session.refresh(user)
    return amount


def consume_hold(
    db_session: Any,
    user: Any,
    *,
    amount_cents: int,
) -> int:
    """Reduce hold after real usage was deducted from balance (avoid double-reserve)."""
    if is_unlimited_user(user) or amount_cents <= 0:
        return 0
    amount = min(int(amount_cents), get_held_cents(user))
    if amount <= 0:
        return 0
    UserModel = type(user)
    updated = (
        db_session.query(UserModel)
        .filter(
            UserModel.id == user.id,
            UserModel.credit_held_cents >= amount,
        )
        .update(
            {UserModel.credit_held_cents: UserModel.credit_held_cents - amount},
            synchronize_session=False,
        )
    )
    if updated != 1:
        db_session.refresh(user)
        return 0
    db_session.refresh(user)
    return amount


def release_job_hold(
    db_session: Any,
    user: Any | None,
    job: Any,
) -> int:
    """Release ``job.held_cents`` back to the user; only clear what was released."""
    held = int(getattr(job, "held_cents", 0) or 0)
    if held <= 0:
        if hasattr(job, "held_cents"):
            job.held_cents = 0
        return 0
    released = 0
    if user is not None:
        released = release_hold(db_session, user, amount_cents=held)
    # Keep remainder marker if release raced / failed — reclaim can retry.
    if hasattr(job, "held_cents"):
        job.held_cents = max(0, held - int(released or 0))
    return released


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
    if amount_eur_cents <= 0:
        raise ValueError("amount_eur_cents must be positive")
    UserModel = type(user)
    (
        db_session.query(UserModel)
        .filter(UserModel.id == user.id)
        .update(
            {
                UserModel.credit_balance_cents: UserModel.credit_balance_cents
                + amount_eur_cents
            },
            synchronize_session=False,
        )
    )
    db_session.refresh(user)
    new_balance = int(user.credit_balance_cents or 0)
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
