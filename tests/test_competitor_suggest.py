"""Auto competitor suggestion for Plus snapshot."""

from __future__ import annotations

from services.competitor_suggest import (
    normalize_competitor_url,
    suggest_competitors,
)


def test_normalize_skips_same_host_and_social():
    assert normalize_competitor_url("https://centropic.ai/foo", seed_host="centropic.ai") is None
    assert normalize_competitor_url("https://facebook.com/x", seed_host="centropic.ai") is None
    assert (
        normalize_competitor_url("surferseo.com", seed_host="centropic.ai")
        == "https://surferseo.com/"
    )


def test_suggest_centropic_uses_vertical_seeds(monkeypatch):
    monkeypatch.setattr(
        "services.competitor_suggest._snippet_context",
        lambda url, timeout=12.0: {
            "url": url,
            "domain": "centropic.ai",
            "title": "Centropic",
            "description": "AIO GEO",
            "outbound_hosts": "",
        },
    )
    monkeypatch.setattr(
        "services.competitor_suggest.assert_public_http_url",
        lambda url, resolve=True: url if url.startswith("http") else "https://" + url,
    )
    out = suggest_competitors("https://centropic.ai/", api_key="", limit=3)
    assert out["domain"] == "centropic.ai"
    assert len(out["competitors"]) == 3
    joined = " ".join(out["competitors"])
    assert "surferseo.com" in joined
    assert "peec.ai" in joined
    assert "otterly.ai" in joined
    assert out["source"] in {"seed", "mixed", "heuristic"}
