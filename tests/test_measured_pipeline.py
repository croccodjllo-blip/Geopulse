"""Unit tests for measured-only pipeline (no crawl)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.measured_pipeline import result_skeleton_from_site, run_measured_only_pipeline


def test_result_skeleton_from_site_reads_crawl_blob():
    site = SimpleNamespace(
        domain="example.com",
        page_title="Ex",
        aio_score=61,
        geo_score=55,
        findings=[{"title": "llms"}],
        analysis_notes=None,
        pages_analyzed=3,
        crawl_pages_json=json.dumps(
            {
                "pages": [{"url": "https://example.com/"}],
                "probes": {"llms": {"ok": True}},
                "signals": {"sov_proxy": {"rate": 0.1}},
                "competitors": [{"domain": "rival.com"}],
            }
        ),
    )
    result = result_skeleton_from_site(site, url="https://example.com/")
    assert result["scraped"]["domain"] == "example.com"
    assert result["aio_score"] == 61
    assert result["signals"]["sov_proxy"]["rate"] == 0.1
    assert result["competitors"][0]["domain"] == "rival.com"


def test_run_measured_only_merges_signals(monkeypatch):
    site = SimpleNamespace(
        id=7,
        user_id=1,
        domain="brand.test",
        page_title="Brand",
        aio_score=50,
        geo_score=50,
        findings=[],
        analysis_notes=None,
        pages_analyzed=1,
        crawl_pages_json=json.dumps(
            {"pages": [], "probes": {}, "signals": {}, "competitors": []}
        ),
        organization_id=None,
        updated_at=None,
    )

    class _Q:
        def filter_by(self, **kw):
            return self

        def first(self):
            return site

    SiteAnalysis = SimpleNamespace(query=_Q())
    AnalysisRun = MagicMock()
    db = MagicMock()
    user = SimpleNamespace(
        id=1,
        company="Brand",
        is_pro=True,
        plan="plus",
        is_admin=False,
    )

    monkeypatch.setattr(
        "services.measured_pipeline.should_run_measured",
        lambda **kw: True,
    )
    monkeypatch.setattr(
        "services.measured_pipeline.user_can_run_measured",
        lambda u: True,
    )
    monkeypatch.setattr(
        "services.measured_pipeline.resolve_prompts",
        lambda **kw: ["prompt"],
    )
    monkeypatch.setattr(
        "services.measured_pipeline.run_citation_monitor",
        lambda **kw: {
            "available": True,
            "evidence": "measured",
            "brand_mention_rate": 0.4,
            "engines": [{"id": "openai", "evidence": "measured", "mention_rate": 0.4}],
            "findings": [],
        },
    )
    monkeypatch.setattr(
        "services.measured_pipeline.persist_sov_snapshot",
        lambda *a, **k: None,
    )

    out = run_measured_only_pipeline(
        db_session=db,
        SiteAnalysis=SiteAnalysis,
        AnalysisRun=AnalysisRun,
        user=user,
        url="https://brand.test/",
        SovSnapshot=object,
    )
    assert out is site
    blob = json.loads(site.crawl_pages_json)
    assert blob["signals"]["sov_measured"]["evidence"] == "measured"
    db.commit.assert_called()
