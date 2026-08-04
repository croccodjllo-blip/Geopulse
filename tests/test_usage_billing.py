"""Tests for usage-based billing system."""
from __future__ import annotations

import pytest

from services.usage_billing import (
    consume_hold,
    release_job_hold,
    GRACE_MARGIN,
    MAX_PREFLIGHT_WORDS,
    estimate_analysis_cost,
    estimate_improvement,
    get_balance_cents,
    giant_page_required_cost_cents,
    has_sufficient_credit,
    PLATFORM_SPREAD,
    check_page_word_budget,
    required_credit_with_grace_cents,
    is_unlimited_user,
    debit_cents_from_usage,
    _model_price,
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
    # llms.txt + openai SoV (5 prompt calls)
    assert len(est.breakdown) == 2
    assert est.estimated_calls == 6
    assert est.raw_cost_usd_micro > 0
    # Per-call ceil: 6 AI calls → ≥6¢ (matches realtime debit shape)
    assert est.service_cost_eur_cents == 6


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
    assert len(est.breakdown) == 4   # llms + 3 probe groups
    # 1 llms + 5 openai + 3 pplx + 3 anthropic = 12 calls
    assert est.estimated_calls == 12
    assert est.service_cost_eur_cents == 12


def test_estimate_mirrors_per_call_ceil_not_bulk_round():
    """Aggregating tokens then rounding once would under-bill measured runs."""
    est = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        anthropic_model="claude-haiku-4-5-20251001",
        perplexity_model="sonar",
        run_measured=True,
        n_prompts=5,
        has_openai=True,
        has_perplexity=True,
        has_anthropic=True,
        has_gemini=True,
        has_xai=True,
    )
    assert est.estimated_calls == 18
    assert est.service_cost_eur_cents == 18
    hold = required_credit_with_grace_cents(est.service_cost_eur_cents)
    assert hold == 20


def test_estimate_runtime_prompt_cap_eight():
    """App uses ANALYSIS_SOV_PROMPTS=8 to match citation_monitor max."""
    est = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        anthropic_model="claude-haiku-4-5-20251001",
        perplexity_model="sonar",
        run_measured=True,
        n_prompts=8,
        has_openai=True,
        has_perplexity=True,
        has_anthropic=True,
        has_gemini=True,
        has_xai=True,
        has_azure=True,
    )
    # 1 llms + 8 oai + 3*5 other engines = 1+8+15 = 24
    assert est.estimated_calls == 24
    assert est.service_cost_eur_cents == 24


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
    def __init__(self, balance: int = 0, role: str = "user"):
        self.credit_balance_cents = balance
        self.role = role


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


def test_required_credit_with_grace_is_higher():
    base = 1_000
    required = required_credit_with_grace_cents(base)
    assert required >= base
    assert required == pytest.approx(int(base * (1 + GRACE_MARGIN)), abs=1)


def test_has_sufficient_credit_needs_grace_margin():
    est = estimate_analysis_cost(
        openai_model="gpt-4o-mini",
        anthropic_model="claude-haiku-4-5-20251001",
        perplexity_model="sonar",
        run_measured=False,
        has_openai=True,
    )
    # Exactly estimated cost is not enough anymore: grace margin required.
    user_exact = _FakeUser(est.service_cost_eur_cents)
    assert has_sufficient_credit(user_exact, est) is False
    user_grace = _FakeUser(required_credit_with_grace_cents(est.service_cost_eur_cents))
    assert has_sufficient_credit(user_grace, est) is True


def test_admin_is_unlimited():
    admin = _FakeUser(0, role="admin")
    assert is_unlimited_user(admin) is True


# ── Improvement preview ──────────────────────────────────────────────────────

def test_improvement_first_time_is_diagnosis_not_uplift():
    imp = estimate_improvement(existing_site=None, run_measured=False, crawl_pages=8)
    assert imp.current_aio is None
    assert imp.improvement_label == "Prima diagnosi"
    assert "guadagno" in imp.improvement_detail.lower() or "dipende" in imp.improvement_detail.lower()


def test_improvement_reanalysis_is_remeasure():
    class _Site:
        aio_score = 60
        geo_score = 55
        def __init__(self):
            self.rating = {"code": "C"}

    imp = estimate_improvement(existing_site=_Site(), run_measured=False, crawl_pages=8)
    assert imp.current_aio == 60
    assert imp.improvement_label == "Ri-misurazione"
    assert "garantito" in imp.improvement_detail.lower()


def test_improvement_measured_noted_not_as_score_boost():
    imp_no = estimate_improvement(existing_site=None, run_measured=False, crawl_pages=8)
    imp_yes = estimate_improvement(existing_site=None, run_measured=True, crawl_pages=8)
    assert "Misurato" in imp_yes.improvement_detail
    assert "Misurato" not in imp_no.improvement_detail


def test_giant_page_required_cost_cents_scales_up():
    base = 100
    scaled = giant_page_required_cost_cents(base, MAX_PREFLIGHT_WORDS * 2)
    assert scaled > base


def test_check_page_word_budget_blocks_when_giant(monkeypatch):
    monkeypatch.setattr("services.usage_billing.preflight_word_count", lambda _url: MAX_PREFLIGHT_WORDS + 5000)
    out = check_page_word_budget(
        url="https://example.com",
        base_cost_cents=100,
        balance_cents=50,
    )
    assert out.is_giant is True
    assert out.required_cost_cents > 100
    assert "Pagina molto grande" in out.message


def test_check_page_word_budget_ok(monkeypatch):
    monkeypatch.setattr("services.usage_billing.preflight_word_count", lambda _url: 900)
    out = check_page_word_budget(
        url="https://example.com",
        base_cost_cents=100,
        balance_cents=1000,
    )
    assert out.is_giant is False


def test_check_page_word_budget_allows_giant_when_funded(monkeypatch):
    monkeypatch.setattr(
        "services.usage_billing.preflight_word_count",
        lambda _url: MAX_PREFLIGHT_WORDS + 5000,
    )
    out = check_page_word_budget(
        url="https://example.com",
        base_cost_cents=100,
        balance_cents=10_000,
    )
    assert out.is_giant is False
    assert out.required_cost_cents > 100


def test_model_price_prefers_longer_sonar_keys():
    assert _model_price("sonar-pro")["in"] == pytest.approx(3.00)
    assert _model_price("sonar-reasoning")["out"] == pytest.approx(5.00)
    assert _model_price("sonar")["in"] == pytest.approx(1.00)


def test_debit_cents_from_usage():
    assert debit_cents_from_usage(0) == 0
    assert debit_cents_from_usage(0.1) == 1
    assert debit_cents_from_usage(1.2) == 2


def test_plan_admin_is_unlimited():
    user = _FakeUser(0, role="user")
    user.plan = "admin"
    user.is_admin = True
    assert is_unlimited_user(user) is True


def test_estimate_uses_ceil_not_truncate():
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
    # With all providers, cost must remain a positive integer cents value.
    assert isinstance(est.service_cost_eur_cents, int)
    assert est.service_cost_eur_cents >= 1


def test_consume_hold_returns_zero_when_update_misses(monkeypatch):
    """Stale in-memory held must not shrink job markers without a DB match."""
    class _Q:
        def filter(self, *a, **k):
            return self
        def update(self, *a, **k):
            return 0

    class _Sess:
        def query(self, model):
            return _Q()
        def refresh(self, user):
            pass

    class _User:
        id = 1
        role = "user"
        plan = "free"
        credit_held_cents = 500

    assert consume_hold(_Sess(), _User(), amount_cents=100) == 0


def test_release_job_hold_keeps_remainder_when_release_fails(monkeypatch):
    monkeypatch.setattr(
        "services.usage_billing.release_hold", lambda *a, **k: 0
    )
    job = type("J", (), {"held_cents": 250})()
    user = type("U", (), {"id": 1, "role": "user", "plan": "free", "credit_held_cents": 250})()
    released = release_job_hold(None, user, job)
    assert released == 0
    assert job.held_cents == 250
