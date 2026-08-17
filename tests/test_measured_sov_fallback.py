"""Measured SoV honesty: zero hits show 0, not proxy share."""

from __future__ import annotations

from services.engine_breakdown import apply_measured_sov, compute_engine_breakdown


def _proxy() -> dict:
    return compute_engine_breakdown(
        aio_score=96,
        geo_score=100,
        findings=[],
        robots_text="User-agent: *\nAllow: /\n",
        competitors=None,
    )


def test_all_zero_measured_shows_zero_brand_sov():
    proxy = _proxy()
    assert proxy["brand_sov"] > 20
    measured = {
        "available": True,
        "brand_mention_rate": 0,
        "engines": [
            {"id": "openai", "mention_rate": 0, "evidence": "measured"},
            {"id": "perplexity", "mention_rate": 0, "evidence": "measured"},
            {"id": "anthropic", "mention_rate": 0, "evidence": "measured"},
            {"id": "google", "mention_rate": 0, "evidence": "measured"},
            {"id": "xai", "mention_rate": 0, "evidence": "measured"},
            {"id": "bing", "mention_rate": 0, "evidence": "measured"},
        ],
    }
    out = apply_measured_sov(proxy, measured)
    assert out["brand_sov"] == 0
    assert out.get("measured_zero_all") is True
    assert out["evidence"] == "measured"
    label = (out.get("label") or "").lower()
    note = (out.get("note") or "").lower()
    assert "0 menzioni" in label or "0 menzioni" in note
    zeroed = [e for e in out["engines"] if e.get("measured_zero")]
    assert len(zeroed) >= 4
    assert all(e.get("propensity") == 0 for e in zeroed)


def test_sparse_measured_zeros_engine_propensity_not_proxy():
    proxy = _proxy()
    measured = {
        "available": True,
        "brand_mention_rate": 12,
        "engines": [
            {"id": "openai", "mention_rate": 12, "evidence": "measured", "samples": 8},
            {"id": "perplexity", "mention_rate": 0, "evidence": "measured"},
            {"id": "anthropic", "mention_rate": 0, "evidence": "measured"},
            {"id": "google", "mention_rate": 0, "evidence": "measured"},
            {"id": "xai", "mention_rate": 0, "evidence": "measured"},
            {"id": "bing", "mention_rate": 0, "evidence": "measured"},
        ],
    }
    out = apply_measured_sov(proxy, measured)
    assert out["brand_sov"] == 12
    assert out["evidence"] == "mixed"
    openai = next(e for e in out["engines"] if e["id"] == "openai")
    google = next(e for e in out["engines"] if e["id"] == "google")
    assert openai["propensity"] == 12
    assert openai["evidence"] == "measured"
    assert google["propensity"] == 0
    assert google.get("mention_rate") == 0
    assert google.get("measured_zero") is True


def test_strong_measured_overrides_brand_sov():
    proxy = _proxy()
    measured = {
        "available": True,
        "brand_mention_rate": 41,
        "engines": [
            {"id": "openai", "mention_rate": 48, "evidence": "measured"},
            {"id": "perplexity", "mention_rate": 36, "evidence": "measured"},
            {"id": "anthropic", "mention_rate": 30, "evidence": "measured"},
        ],
    }
    out = apply_measured_sov(proxy, measured)
    assert out["brand_sov"] == 41
    assert out["evidence"] == "mixed"
    openai = next(e for e in out["engines"] if e["id"] == "openai")
    assert openai["propensity"] == 48
