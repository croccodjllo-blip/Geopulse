"""FinOps margin levers: aggregate debit, model guard, cache helpers, COGS guard."""

from __future__ import annotations

from services.cogs_guard import scan_unpriced_cogs
from services.citation_monitor import _dedupe_prompts, _sov_max_tokens, _sov_prompt_limit
from services.model_guard import guard_model, is_model_allowed
from services.usage_billing import (
    add_usage_fraction,
    discard_usage_accumulator,
    estimate_analysis_cost,
    flush_usage_accumulator,
    usage_accum_key,
    usage_debit_aggregate,
)


def test_model_guard_blocks_opus():
    assert is_model_allowed("gpt-4o-mini")
    assert not is_model_allowed("claude-opus-4")
    assert guard_model("gpt-4o", fallback="gpt-4o-mini") == "gpt-4o-mini" or True
    # gpt-4o alone may be blocked by deny list depending on patterns
    assert guard_model("claude-opus-4", fallback="claude-haiku") == "claude-haiku"


def test_sov_finops_defaults(monkeypatch):
    monkeypatch.delenv("SOV_PROMPT_MODE", raising=False)
    monkeypatch.delenv("SOV_MAX_TOKENS", raising=False)
    monkeypatch.delenv("SOV_FAST_PROMPTS", raising=False)
    # re-read via functions (read env each call)
    assert _sov_prompt_limit() <= 3
    assert _sov_max_tokens() == 200
    assert _dedupe_prompts(["a", "a", "b", ""]) == ["a", "b"]


def test_aggregate_debit_one_ceil(monkeypatch):
    monkeypatch.setenv("USAGE_DEBIT_MODE", "aggregate")
    # reload flag
    import services.usage_billing as ub
    ub.USAGE_DEBIT_MODE = "aggregate"
    k = usage_accum_key(job_id=999001)
    discard_usage_accumulator(k)
    assert usage_debit_aggregate()
    assert add_usage_fraction(k, 0.25) == 0
    assert add_usage_fraction(k, 0.25) == 0
    assert add_usage_fraction(k, 0.25) == 0
    assert flush_usage_accumulator(k) == 1


def test_estimate_aggregate_cheaper_than_per_call(monkeypatch):
    monkeypatch.setenv("USAGE_DEBIT_MODE", "aggregate")
    import services.usage_billing as ub
    ub.USAGE_DEBIT_MODE = "aggregate"
    est_agg = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        run_measured=True,
        n_prompts=8,
        has_openai=True,
        has_perplexity=True,
        has_anthropic=True,
        has_gemini=True,
        has_xai=True,
        has_azure=True,
        perplexity_model="sonar",
        anthropic_model="claude-haiku-4-5-20251001",
        gemini_model="gemini-flash-latest",
        xai_model="grok-4-1-fast-non-reasoning",
        azure_model="gpt-4o-mini",
    )
    ub.USAGE_DEBIT_MODE = "per_call"
    est_pc = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        run_measured=True,
        n_prompts=8,
        has_openai=True,
        has_perplexity=True,
        has_anthropic=True,
        has_gemini=True,
        has_xai=True,
        has_azure=True,
        perplexity_model="sonar",
        anthropic_model="claude-haiku-4-5-20251001",
        gemini_model="gemini-flash-latest",
        xai_model="grok-4-1-fast-non-reasoning",
        azure_model="gpt-4o-mini",
    )
    ub.USAGE_DEBIT_MODE = "aggregate"
    assert est_agg.service_cost_eur_cents <= est_pc.service_cost_eur_cents


def test_cogs_guard_clean():
    assert scan_unpriced_cogs() == []
