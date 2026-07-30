"""Child sitemap fetches must stay on the same host."""

from __future__ import annotations

from services.analyzer import canonicalize_sitemap_url, collect_sitemap_urls


def test_canonicalize_sitemap_url_same_host():
    seed = "https://example.com/"
    assert (
        canonicalize_sitemap_url("https://example.com/sitemap-posts.xml", seed=seed)
        == "https://example.com/sitemap-posts.xml"
    )
    assert canonicalize_sitemap_url("https://evil.example/x.xml", seed=seed) is None
    assert canonicalize_sitemap_url("https://169.254.169.254/latest", seed=seed) is None


def test_collect_sitemap_skips_cross_host_children(monkeypatch):
    called: list[str] = []

    def fake_safe_get(session, url, **kwargs):
        called.append(url)
        raise AssertionError(f"should not fetch {url}")

    monkeypatch.setattr("services.analyzer.safe_get", fake_safe_get)
    xml = """<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://evil.test/private.xml</loc></sitemap>
      <sitemap><loc>http://127.0.0.1/sitemap.xml</loc></sitemap>
    </sitemapindex>
    """
    out = collect_sitemap_urls(
        "https://example.com/",
        {"ok": True, "snippet": xml},
        limit=10,
    )
    assert out == []
    assert called == []
