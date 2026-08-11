"""JS crawl enrich hooks on scrape_page (thin SPA shells only)."""

from __future__ import annotations

import services.analyzer as analyzer


class _FakeResp:
    def __init__(self, text: str, *, url: str = "https://example.com/", status: int = 200):
        self.text = text
        self.url = url
        self.status_code = status
        self.headers = {"Content-Type": "text/html"}
        self.history: list = []


def test_should_js_enrich_spa_shell():
    html = '<html><body><div id="root"></div><script src="/app.js"></script></body></html>'
    scraped = {"word_count": 5, "status_code": 200, "blocking_scripts": 1}
    assert analyzer._should_js_enrich(scraped, html) is True


def test_should_not_js_enrich_contentful_page():
    html = "<html><body><h1>Hello</h1><p>" + ("word " * 100) + "</p></body></html>"
    scraped = {"word_count": 100, "status_code": 200, "blocking_scripts": 0}
    assert analyzer._should_js_enrich(scraped, html) is False


def test_scrape_page_playwright_enrich(monkeypatch):
    thin = (
        '<!doctype html><html><head><title>App</title></head>'
        '<body><div id="root"></div>'
        '<script src="/bundle.js"></script></body></html>'
    )
    rich = (
        "<!doctype html><html><head><title>App</title>"
        '<script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script>'
        "</head><body><h1>Acme Brand</h1><p>"
        + ("Visible content for generative crawlers. " * 30)
        + "</p></body></html>"
    )

    monkeypatch.setattr(
        analyzer,
        "safe_get",
        lambda *a, **k: _FakeResp(thin),
    )
    monkeypatch.setattr(analyzer, "js_crawl_available", lambda: True)
    monkeypatch.setattr(
        analyzer,
        "render_html",
        lambda url, **k: {"ok": True, "html": rich, "error": None, "mode": "playwright"},
    )
    monkeypatch.setattr(
        analyzer,
        "assert_public_http_url",
        lambda u, resolve=False: u if u.startswith("http") else "https://" + u,
    )

    out = analyzer.scrape_page("https://example.com/", allow_js=True)
    assert out["fetch_mode"] == "playwright"
    assert out.get("js_enriched") is True
    assert int(out["word_count"]) > 80


def test_scrape_page_allow_js_false_skips_playwright(monkeypatch):
    thin = (
        '<!doctype html><html><body><div id="root"></div>'
        '<script src="/bundle.js"></script></body></html>'
    )
    called = {"n": 0}

    monkeypatch.setattr(analyzer, "safe_get", lambda *a, **k: _FakeResp(thin))
    monkeypatch.setattr(analyzer, "js_crawl_available", lambda: True)

    def _boom(url, **k):
        called["n"] += 1
        return {"ok": True, "html": "<html><body>x</body></html>", "error": None}

    monkeypatch.setattr(analyzer, "render_html", _boom)
    monkeypatch.setattr(
        analyzer,
        "assert_public_http_url",
        lambda u, resolve=False: u if u.startswith("http") else "https://" + u,
    )

    out = analyzer.scrape_page("https://example.com/", allow_js=False)
    assert called["n"] == 0
    assert out["fetch_mode"] == "static"
