"""score_site must tolerate crawl pages with aio_score/geo_score=None."""

from __future__ import annotations

from services.analyzer import score_site


def _base_scraped() -> dict:
    return {
        "title": "Example Brand Official Site",
        "description": "A long enough meta description for generative engines and GEO.",
        "jsonld": {},
        "html_faq": {},
        "entity": {},
        "canonical": "https://example.com/",
        "og_title": "Example",
        "og_description": "desc",
        "has_h1": True,
        "lang": "en",
        "robots": "",
        "domain": "example.com",
        "headings": ["About"],
        "links": [],
        "snippet": "hello",
        "word_count": 200,
        "final_url": "https://example.com/",
    }


def _probes() -> dict:
    return {
        "llms": {"ok": False},
        "robots": {"ok": True, "snippet": "User-agent: *\nAllow: /\n"},
        "sitemap": {
            "ok": True,
            "url": "/sitemap.xml",
            "urls": ["https://example.com/", "https://example.com/a"],
        },
    }


def test_score_site_ignores_none_page_scores():
    pages = [
        {
            "url": "https://example.com/",
            "title": "Home",
            "description": "x" * 60,
            "word_count": 120,
            "aio_score": 70,
            "geo_score": 65,
            "issues": [],
            "status_code": 200,
            "response_ms": 100,
            "scraped": {"internal_hrefs": [], "description": "x" * 60},
        },
        {
            "url": "https://example.com/blocked",
            "title": "",
            "description": "",
            "word_count": 0,
            "aio_score": None,
            "geo_score": None,
            "issues": ["crawl_fetch_failed"],
            "status_code": None,
            "response_ms": None,
            "scraped": {},
            "crawl_error": "timeout",
        },
        {
            "url": "https://cdn.example.net/x",
            "title": "",
            "aio_score": None,
            "geo_score": None,
            "issues": ["off_domain_redirect"],
            "scraped": {"word_count": 0},
            "crawl_error": "off_domain_redirect",
        },
    ]
    result = score_site(
        "https://example.com/",
        _base_scraped(),
        _probes(),
        page_reports=pages,
    )
    assert isinstance(result["aio_score"], (int, float))
    assert isinstance(result["geo_score"], (int, float))
    titles = {f.get("title") for f in result["findings"]}
    assert any("non scorabili" in t for t in titles if isinstance(t, str))
