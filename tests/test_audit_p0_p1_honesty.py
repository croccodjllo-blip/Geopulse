"""Audit P0/P1: Business waitlist, waiver fail-closed, zero-hit SoV honesty."""

from __future__ import annotations

from pathlib import Path

from services.engine_breakdown import apply_measured_sov, compute_engine_breakdown
from services.paddle_billing import client_config, paddle_business_enabled, sell_plus_only
from services.prompt_bank import resolve_prompts


def test_business_waitlist_hides_price_ids(monkeypatch):
    monkeypatch.setenv("SELL_PLUS_ONLY", "1")
    monkeypatch.setenv("PADDLE_CLIENT_TOKEN", "tok_test")
    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_plus")
    monkeypatch.setenv("PADDLE_PRICE_BUSINESS_MONTHLY", "pri_biz")
    assert sell_plus_only() is True
    assert paddle_business_enabled() is False
    cfg = client_config()
    assert cfg["businessReady"] is False
    assert cfg["priceBusiness"] == ""
    assert cfg["priceBusinessYearly"] == ""


def test_pricing_template_has_no_business_checkout():
    pricing = Path("templates/pricing.html").read_text(encoding="utf-8")
    biz = pricing[pricing.index('id="business"') :]
    assert 'data-paddle-checkout="business"' not in biz
    assert "Paga Business" not in biz
    assert "Waitlist" in biz or "waitlist" in biz.lower() or "Richiedi onboarding" in biz


def test_paddle_js_waiver_fail_closed():
    js = Path("static/js/paddle-checkout.js").read_text(encoding="utf-8")
    assert "opening checkout anyway" not in js
    assert "checkout blocked" in js
    assert "businessReady" in js


def test_zero_hit_measured_shows_zero_not_proxy():
    proxy = compute_engine_breakdown(
        aio_score=96,
        geo_score=100,
        findings=[],
        robots_text="User-agent: *\nAllow: /\n",
        competitors=None,
    )
    assert proxy["brand_sov"] > 20
    measured = {
        "available": True,
        "brand_mention_rate": 0,
        "engines": [
            {"id": e, "mention_rate": 0, "evidence": "measured"}
            for e in ("openai", "perplexity", "anthropic", "google", "xai", "bing")
        ],
    }
    out = apply_measured_sov(proxy, measured)
    assert out.get("measured_zero_all") is True
    assert out["brand_sov"] == 0
    assert out["evidence"] == "measured"
    assert "0 menzioni" in (out.get("label") or "").lower()
    note = (out.get("note") or "").lower()
    assert "0%" in note or "0 menzioni" in note
    assert "stimata" not in note or "non riusiamo" in note


def test_resolve_prompts_scoped_to_domain():
    prompts = resolve_prompts(
        user=None,
        locale="it",
        domain="acme-tools.it",
        brand="Acme Tools",
        own_site=True,
    )
    blob = " ".join(prompts).lower()
    assert "acme" in blob
    assert "centropic" not in blob


def test_landing_hero_readiness_not_citations_promise():
    landing = Path("templates/landing.html").read_text(encoding="utf-8")
    assert "ti citano" not in landing.split("{% block content %}", 1)[-1][:2500]
    assert "readiness" in landing.lower() or "Misura la readiness" in landing
