"""Tests for usage-based billing system."""
from __future__ import annotations

import pytest

from services.usage_billing import (
    estimate_analysis_cost,
    estimate_improvement,
    get_balance_cents,
    has_sufficient_credit,
    PLATFORM_SPREAD,
    _model_price,
    _next_rating,
)


# ── Price table ─────────────────────────────────────────────────────────────

def test_model_price_gpt4o_mini():
    p = _model_price("gpt-4o-mini")
    assert p["in"] == pytest.approx(0.15)
    assert p["out"] == pytest.approx(0.60)


def test_model_price_claude_haiku():
    p = _model_price("claude-haiku-4-5-20251001")
    assert p["in"] == pytest.approx(0.80)


def test_model_price_unknown_fallback():
    p = _model_price("unknown-model-xyz")
    assert p["in"] > 0


# ── Cost estimate ────────────────────────────────────────────────────────────

def test_estimate_basic_no_measured():
    est = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        anthropic_model="claude-haiku-4-5-20251001",
        perplexity_model="sonar",
        run_measured=False,
        has_openai=True,
        has_perplexity=False,
        has_anthropic=False,
    )
    assert est.service_cost_eur_cents >= 1
    # Spread applied correctly
    assert est.service_cost_usd_micro == pytest.approx(
        est.raw_cost_usd_micro * (1 + PLATFORM_SPREAD), rel=1e-6
    )
    assert len(est.breakdown) == 1  # only llms.txt


def test_estimate_with_measured_openai_only():
    est = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        anthropic_model="claude-haiku-4-5-20251001",
        perplexity_model="sonar",
        run_measured=True,
        n_prompts=5,
        has_openai=True,
        has_perplexity=False,
        has_anthropic=False,
    )
    # llms.txt + openai SoV
    assert len(est.breakdown) == 2
    assert est.raw_cost_usd_micro > 0


def test_estimate_all_providers_measured():
    est = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        anthropic_model="claude-haiku-4-5-20251001",
        perplexity_model="sonar",
        run_measured=True,
        n_prompts=5,
        has_openai=True,
        has_perplexity=True,
        has_anthropic=True,
    )
    assert len(est.breakdown) == 4   # llms + 3 probes
    assert est.service_cost_eur_cents >= 1


def test_estimate_as_dict():
    est = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        anthropic_model="claude-haiku-4-5-20251001",
        perplexity_model="sonar",
        run_measured=False,
        has_openai=True,
    )
    d = est.as_dict()
    assert "service_cost_eur_cents" in d
    assert d["spread_pct"] == round(PLATFORM_SPREAD * 100)
    assert d["service_cost_eur"] == pytest.approx(est.service_cost_eur, rel=1e-4)


def test_spread_77_pct():
    """Platform spread must be exactly 77% of raw cost."""
    est = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        anthropic_model="claude-haiku-4-5-20251001",
        perplexity_model="sonar",
        run_measured=False,
        has_openai=True,
    )
    assert est.service_cost_usd_micro == pytest.approx(est.raw_cost_usd_micro * 1.77, rel=1e-6)


# ── Credit helpers ───────────────────────────────────────────────────────────

class _FakeUser:
    def __init__(self, balance: int = 0):
        self.credit_balance_cents = balance


def test_get_balance_cents():
    assert get_balance_cents(_FakeUser(500)) == 500
    assert get_balance_cents(_FakeUser(0)) == 0


def test_has_sufficient_credit_ok():
    est = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        anthropic_model="claude-haiku-4-5-20251001",
        perplexity_model="sonar",
        run_measured=False,
        has_openai=True,
    )
    user = _FakeUser(10_000)  # 100 EUR
    assert has_sufficient_credit(user, est) is True


def test_has_sufficient_credit_insufficient():
    est = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        anthropic_model="claude-haiku-4-5-20251001",
        perplexity_model="sonar",
        run_measured=False,
        has_openai=True,
    )
    user = _FakeUser(0)
    assert has_sufficient_credit(user, est) is False


# ── Improvement preview ──────────────────────────────────────────────────────

def test_improvement_first_time():
    imp = estimate_improvement(existing_site=None, run_measured=False, crawl_pages=8)
    assert imp.current_aio is None
    assert imp.expected_aio_delta > 0
    assert imp.expected_geo_delta > 0
    assert imp.improvement_label in {"Significativo", "Buono", "Moderato", "Manutenzione"}


def test_improvement_reanalysis():
    class _Site:
        aio_score = 60
        geo_score = 55
        def __init__(self):
            self.rating = {"code": "C"}

    imp = estimate_improvement(existing_site=_Site(), run_measured=False, crawl_pages=8)
    assert imp.current_aio == 60
    assert imp.expected_aio_delta > 0


def test_improvement_measured_boosts_geo():
    imp_no  = estimate_improvement(existing_site=None, run_measured=False, crawl_pages=8)
    imp_yes = estimate_improvement(existing_site=None, run_measured=True,  crawl_pages=8)
    assert imp_yes.expected_geo_delta > imp_no.expected_geo_delta


def test_next_rating():
    assert _next_rating("C") == "B"
    assert _next_rating("AAA") == "AAA"
    assert _next_rating("DDD") == "DD"
    assert _next_rating(None) is None
