"""HTTP hygiene: ads.txt must not 404; /health must not enter HTML crawl."""

from __future__ import annotations

from services.analyzer import canonicalize_page_url


def test_canonicalize_skips_health_and_txt():
    seed = "https://centropic.ai/"
    assert canonicalize_page_url("https://centropic.ai/health", seed=seed) is None
    assert canonicalize_page_url("https://centropic.ai/health/", seed=seed) is None
    assert canonicalize_page_url("https://centropic.ai/ads.txt", seed=seed) is None
    assert canonicalize_page_url("https://centropic.ai/llms.txt", seed=seed) is None
    assert canonicalize_page_url("https://centropic.ai/status", seed=seed) == (
        "https://centropic.ai/status"
    )


def test_http_error_finding_lists_urls():
    from services.deep_checks import analyze_crawl_aggregate

    out = analyze_crawl_aggregate(
        pages=[
            {"url": "https://centropic.ai/ads.txt", "status_code": 404},
            {"url": "https://centropic.ai/faq", "status_code": 200, "response_ms": 100},
        ],
        sitemap_urls=["https://centropic.ai/faq"],
        seed_url="https://centropic.ai/",
    )
    crit = [f for f in out["findings"] if f.get("severity") == "critical"]
    assert crit
    assert "ads.txt" in crit[0]["detail"]
