"""SEO crawl hygiene: defer detection + canonical legal aliases."""

from __future__ import annotations

from bs4 import BeautifulSoup
from pathlib import Path


def test_boolean_defer_async_not_counted_as_blocking():
    html = """
    <html><head>
      <script src="/a.js" defer></script>
      <script src="/b.js" async></script>
      <script defer="defer" src="/c.js"></script>
      <script async="async" src="/d.js"></script>
      <script src="/block.js"></script>
    </head><body></body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    blocking = 0
    for script in soup.find_all("script"):
        src = script.get("src")
        if not src:
            continue
        if script.has_attr("async") or script.has_attr("defer"):
            continue
        blocking += 1
    assert blocking == 1
    # Production code must use has_attr (empty-string boolean attrs are falsy).
    src = Path("services/analyzer.py").read_text(encoding="utf-8")
    assert "has_attr(\"async\")" in src or "has_attr('async')" in src
    assert 'not script.get("async")' not in src


def test_legal_aliases_redirect_to_canonical():
    from app import app

    cases = {
        "/cookies": "/cookie",
        "/cookie-policy": "/cookie",
        "/terms": "/termini",
        "/refund": "/rimborsi",
        "/refund-policy": "/rimborsi",
        "/contact": "/contatti",
        "/trust-security": "/trust",
        "/security": "/trust",
        "/accessibility": "/accessibilita",
        "/ai-transparency": "/ai",
        "/trasparenza-ai": "/ai",
        "/sub-responsabili": "/dpa",
    }
    with app.test_client() as client:
        for alias, canonical in cases.items():
            resp = client.get(alias, follow_redirects=False)
            assert resp.status_code == 301, alias
            loc = resp.headers.get("Location", "")
            assert loc.endswith(canonical) or canonical in loc, (alias, loc, canonical)


def test_canonical_legal_pages_200():
    from app import app

    with app.test_client() as client:
        for path in ("/cookie", "/termini", "/rimborsi", "/contatti", "/trust", "/dpa", "/ai"):
            assert client.get(path).status_code == 200, path


def test_cookie_page_has_legal_rail_links():
    from app import app

    html = app.test_client().get("/cookie").get_data(as_text=True)
    assert 'class="legal-rail"' in html
    assert "/privacy" in html
    assert "/termini" in html
    assert "/trust" in html
