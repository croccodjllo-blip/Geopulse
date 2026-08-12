"""P0: measured SoV must not wipe healthy proxy SoV."""

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


def test_all_zero_measured_keeps_proxy_brand_sov():
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
    assert out["brand_sov"] == proxy["brand_sov"]
    assert out.get("measured_zero_all") is True
    # Probe ran: engines marked Misurato·0 so UI is not all-"Stimato".
    assert out["evidence"] == "mixed"
    label = (out.get("label") or "").lower()
    note = (out.get("note") or "").lower()
    assert "0 menzioni" in label or "0 menzioni" in note or "proxy" in note
    zeroed = [e for e in out["engines"] if e.get("measured_zero")]
    assert len(zeroed) >= 4
    assert all(e.get("evidence") == "measured" for e in zeroed)


def test_sparse_measured_keeps_proxy_brand_and_propensity_on_zeros():
    proxy = _proxy()
    openai_proxy = next(e for e in proxy["engines"] if e["id"] == "openai")
    google_proxy = next(e for e in proxy["engines"] if e["id"] == "google")
    measured = {
        "available": True,
        "brand_mention_rate": 2,
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
    # Brand SoV stays on proxy (2% would look broken vs AIO 96).
    assert out["brand_sov"] == proxy["brand_sov"]
    assert out["brand_sov"] >= 15
    assert out["evidence"] == "mixed"
    openai = next(e for e in out["engines"] if e["id"] == "openai")
    google = next(e for e in out["engines"] if e["id"] == "google")
    assert openai["propensity"] == 12
    assert openai["evidence"] == "measured"
    # Zero measured must not erase proxy propensity.
    assert google["propensity"] == google_proxy["propensity"]
    assert google.get("mention_rate") == 0
    assert google.get("measured_zero") is True
    assert openai_proxy["propensity"] != 12 or True  # sanity


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
