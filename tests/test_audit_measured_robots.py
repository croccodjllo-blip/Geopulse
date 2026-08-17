"""Audit fix coverage: measured slot atomicity, robots disallow, entity brand.

Covers the HIGH fixes from the P0/P1 measured+robots audit:
- ``acquire_measured_slot`` reserves atomically (Lua check-and-add, no
  ZADD-then-ZREM overshoot race).
- ``crawl_domain_bfs`` skips robots.txt-disallowed BFS URLs (fail-open when
  robots.txt itself is unreachable/unparseable).
- ``result_skeleton_from_site`` restores the brand entity from crawl signals
  instead of always falling back to the bare domain.
"""

from __future__ import annotations

import json

import services.analyzer as analyzer
from services.measured_pipeline import result_skeleton_from_site
from services.measured_queue import (
    _ACQUIRE_SLOT_LUA,
    acquire_measured_slot,
    release_measured_slot,
)
from services.redis_client import reset_redis_client_for_tests
from tests.test_analyze_redis_queue import _FakeRedis


class _FakeSite:
    def __init__(self, *, crawl_pages_json: str, domain: str, page_title: str | None = None):
        self.crawl_pages_json = crawl_pages_json
        self.domain = domain
        self.page_title = page_title
        self.aio_score = 70
        self.geo_score = 65
        self.findings = []
        self.findings_json = "[]"
        self.analysis_notes = ""
        self.pages_analyzed = 1


# ---------------------------------------------------------------------------
# C) measured slot atomic acquire
# ---------------------------------------------------------------------------


def test_acquire_measured_slot_lua_checks_before_add():
    """The reservation script must gate ZADD behind a ZCARD < cap check."""
    zadd_idx = _ACQUIRE_SLOT_LUA.index("ZADD")
    zcard_idx = _ACQUIRE_SLOT_LUA.index("ZCARD")
    cap_check_idx = _ACQUIRE_SLOT_LUA.index("active >= cap")
    assert zcard_idx < cap_check_idx < zadd_idx, (
        "ZADD must only run after the cap check — otherwise concurrent "
        "callers could both pass a stale ZCARD before either ZADDs."
    )


def test_acquire_measured_slot_never_overshoots_cap(monkeypatch):
    reset_redis_client_for_tests()
    fake = _FakeRedis()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("ANALYZE_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("MAX_CONCURRENT_MEASURED", "3")
    monkeypatch.setattr("services.redis_client.get_redis", lambda ping=True: fake)

    tokens = [acquire_measured_slot() for _ in range(6)]
    granted = [t for t in tokens if t]
    assert len(granted) == 3
    # The underlying zset must never hold more members than the cap allows —
    # exactly the invariant a ZADD-then-ZREM race could violate transiently.
    assert fake.zcard("centropic:measured:holds") == 3

    for t in granted:
        release_measured_slot(t)
    assert fake.zcard("centropic:measured:holds") == 0
    reset_redis_client_for_tests()


# ---------------------------------------------------------------------------
# D) robots.txt disallow gate on BFS extras
# ---------------------------------------------------------------------------


def test_robots_allows_bfs_respects_disallow():
    parser = analyzer._robots_parser_from_probe(
        {"ok": True, "snippet": "User-agent: *\nDisallow: /private\n"}
    )
    assert parser is not None
    assert analyzer._robots_allows_bfs(parser, "https://example.com/private/x") is False
    assert analyzer._robots_allows_bfs(parser, "https://example.com/public") is True


def test_robots_parser_fails_open_without_snippet():
    # No probe / empty snippet (fetch failed or robots.txt missing) → allow.
    assert analyzer._robots_parser_from_probe(None) is None
    assert analyzer._robots_parser_from_probe({}) is None
    assert analyzer._robots_allows_bfs(None, "https://example.com/anything") is True


def test_crawl_domain_bfs_skips_disallowed_urls(monkeypatch):
    seed_scraped = {
        "final_url": "https://example.com/",
        "title": "Home",
        "description": "d" * 60,
    }
    probes = {
        "robots": {"ok": True, "snippet": "User-agent: *\nDisallow: /private\n"},
    }

    monkeypatch.setattr(
        analyzer,
        "discover_domain_urls",
        lambda *a, **k: [
            "https://example.com/public",
            "https://example.com/private/secret",
        ],
    )
    monkeypatch.setattr(
        analyzer,
        "_enqueue_links",
        lambda *a, **k: None,
    )

    fetched: list[str] = []

    def _fake_crawl_extra(urls, *, seed_url, max_workers=4):
        fetched.extend(urls)
        return [
            {
                "url": u,
                "title": "t",
                "aio_score": 80,
                "geo_score": 80,
                "issues": [],
                "scraped": {},
            }
            for u in urls
        ]

    monkeypatch.setattr(analyzer, "_crawl_extra_pages", _fake_crawl_extra)

    reports = analyzer.crawl_domain_bfs(
        "https://example.com/",
        seed_scraped,
        probes,
        max_pages=5,
    )

    assert "https://example.com/private/secret" not in fetched
    assert "https://example.com/public" in fetched
    assert len(reports) >= 1


def test_crawl_domain_bfs_unaffected_when_robots_probe_failed(monkeypatch):
    """robots.txt fetch failure must not block BFS (fail-open, current behavior)."""
    seed_scraped = {
        "final_url": "https://example.com/",
        "title": "Home",
        "description": "d" * 60,
    }
    probes = {"robots": {"ok": False, "snippet": ""}}

    monkeypatch.setattr(
        analyzer,
        "discover_domain_urls",
        lambda *a, **k: ["https://example.com/private/secret"],
    )
    monkeypatch.setattr(analyzer, "_enqueue_links", lambda *a, **k: None)

    fetched: list[str] = []

    def _fake_crawl_extra(urls, *, seed_url, max_workers=4):
        fetched.extend(urls)
        return [
            {"url": u, "title": "t", "aio_score": 80, "geo_score": 80, "issues": [], "scraped": {}}
            for u in urls
        ]

    monkeypatch.setattr(analyzer, "_crawl_extra_pages", _fake_crawl_extra)

    analyzer.crawl_domain_bfs("https://example.com/", seed_scraped, probes, max_pages=5)
    assert "https://example.com/private/secret" in fetched


# ---------------------------------------------------------------------------
# B) entity brand restored from site signals
# ---------------------------------------------------------------------------


def test_result_skeleton_uses_entity_brand_from_signals():
    site = _FakeSite(
        crawl_pages_json=json.dumps(
            {"pages": [], "signals": {"entity": {"brand_name": "Acme Corp"}}}
        ),
        domain="acme.example.com",
    )
    result = result_skeleton_from_site(site, url="https://acme.example.com/")
    assert result["scraped"]["entity"]["brand_name"] == "Acme Corp"


def test_result_skeleton_falls_back_to_domain_without_entity():
    site = _FakeSite(
        crawl_pages_json=json.dumps({"pages": [], "signals": {}}),
        domain="acme.example.com",
    )
    result = result_skeleton_from_site(site, url="https://acme.example.com/")
    assert result["scraped"]["entity"]["brand_name"] == "acme.example.com"


def test_result_skeleton_ignores_blank_entity_brand_name():
    site = _FakeSite(
        crawl_pages_json=json.dumps(
            {"pages": [], "signals": {"entity": {"brand_name": "  "}}}
        ),
        domain="acme.example.com",
    )
    result = result_skeleton_from_site(site, url="https://acme.example.com/")
    assert result["scraped"]["entity"]["brand_name"] == "acme.example.com"
