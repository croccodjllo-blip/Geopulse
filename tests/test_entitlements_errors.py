"""Plan entitlements and analyze error taxonomy."""

from __future__ import annotations

from types import SimpleNamespace

import requests

from services.analyze_errors import classify_analyze_error, format_job_error
from services.entitlements import entitlements_for, require_capability


def _ents(user, **overrides):
    defaults = dict(
        max_sites_free=1,
        max_sites_pro=50,
        free_total_analyses=2,
        pro_daily_analyses=200,
        free_crawl_pages=8,
        pro_crawl_pages=2000,
        pro_crawl_unlimited=True,
        free_history_limit=10,
        pro_history_limit=100,
    )
    defaults.update(overrides)
    return entitlements_for(user, **defaults)


def test_free_cannot_use_plus_capabilities():
    free = SimpleNamespace(plan="free", is_pro=False, is_admin=False)
    ents = _ents(free)
    assert ents.is_pro is False
    assert ents.can("api_access") is False
    assert ents.can("agency_whitelabel") is False
    assert ents.can("measured_sov") is False
    assert ents.can("pack_email") is True
    msg = require_capability(ents, "api_access")
    assert msg and "Plus" in msg


def test_plus_has_full_capabilities():
    plus = SimpleNamespace(plan="plus", is_pro=True, is_admin=False)
    ents = _ents(plus)
    assert ents.is_pro is True
    assert ents.can("api_access") is True
    assert ents.can("full_crawl") is True
    assert ents.crawl_unlimited is True
    assert require_capability(ents, "api_access") is None


def test_classify_timeout_and_http():
    info = classify_analyze_error(requests.Timeout("timed out"))
    assert info["code"] == "timeout"
    assert "Timeout" in info["title"]

    info2 = classify_analyze_error("HTTP 403 su https://example.com")
    assert info2["code"] == "http_403"
    assert "403" in info2["title"]

    info3 = classify_analyze_error("SSL: CERTIFICATE_VERIFY_FAILED")
    assert info3["code"] == "ssl"

    compact = format_job_error(requests.Timeout("read timed out"))
    assert "Timeout" in compact
    assert len(compact) <= 500
