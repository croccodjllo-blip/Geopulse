"""Audit fixes: Stripe Plus tokens, crawl caps, SoV parallel helpers."""

from __future__ import annotations

from types import SimpleNamespace

from services.analyze_eta import estimate_total_seconds
from services.citation_monitor import _sov_engine_parallelism, _sov_prompt_limit


def test_sov_parallelism_bounds(monkeypatch):
    monkeypatch.setenv("SOV_ENGINE_PARALLEL", "99")
    assert _sov_engine_parallelism() == 6
    monkeypatch.setenv("SOV_ENGINE_PARALLEL", "2")
    assert _sov_engine_parallelism() == 2


def test_sov_fast_prompt_mode(monkeypatch):
    monkeypatch.setenv("SOV_PROMPT_MODE", "fast")
    monkeypatch.setenv("SOV_FAST_PROMPTS", "3")
    monkeypatch.setenv("ANALYSIS_SOV_PROMPTS", "8")
    assert _sov_prompt_limit() == 3
    monkeypatch.setenv("SOV_PROMPT_MODE", "full")
    assert _sov_prompt_limit() == 8


def test_eta_measured_faster_after_parallel():
    # Parallel SoV still adds a ~70s probe budget on top of crawl+pack.
    sec = estimate_total_seconds(max_pages=8, run_measured=True, competitor_count=0)
    assert 20 <= sec <= 120
    stimato = estimate_total_seconds(max_pages=8, run_measured=False, competitor_count=0)
    assert stimato < sec


def test_resolve_crawl_pages_default_and_deep(monkeypatch):
    import app as app_mod

    monkeypatch.setattr(app_mod, "FREE_CRAWL_PAGES", 8)
    monkeypatch.setattr(app_mod, "PRO_CRAWL_PAGES", 120)
    monkeypatch.setattr(app_mod, "PRO_CRAWL_UNLIMITED", False)
    monkeypatch.setattr(app_mod, "PRO_DEEP_CRAWL_PAGES", 500)

    free = SimpleNamespace(is_pro=False)
    plus = SimpleNamespace(is_pro=True)
    assert app_mod.resolve_crawl_pages(free) == 8
    assert app_mod.resolve_crawl_pages(plus, deep_crawl=False) == 120
    assert app_mod.resolve_crawl_pages(plus, deep_crawl=True) == 500


def test_grant_plus_monthly_tokens_idempotent(monkeypatch):
    from app import CreditLedger, User, app, db, ensure_schema, grant_plus_monthly_tokens

    with app.app_context():
        ensure_schema()
        user = User(
            email="plus-tokens-audit@example.com",
            name="Plus",
            password_hash="x",
            plan="plus",
            credit_balance_cents=0,
        )
        db.session.add(user)
        db.session.commit()
        ok1 = grant_plus_monthly_tokens(
            user=user, idempotency_key="stripe-plus-tokens:cs_test_1"
        )
        db.session.commit()
        bal1 = int(user.credit_balance_cents or 0)
        ok2 = grant_plus_monthly_tokens(
            user=user, idempotency_key="stripe-plus-tokens:cs_test_1"
        )
        db.session.commit()
        bal2 = int(user.credit_balance_cents or 0)
        assert ok1 is True
        assert ok2 is False
        assert bal1 == bal2
        assert bal1 == 1000
        rows = CreditLedger.query.filter_by(
            stripe_payment_intent="stripe-plus-tokens:cs_test_1"
        ).count()
        assert rows == 1
