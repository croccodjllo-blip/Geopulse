"""GEO Charts insights payload uses native gettext (not raw Italian storage)."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-geo-ui-insights-i18n")

from flask_babel import force_locale

from app import app
from services.geo_ui_payload import build_geo_ui_payload

TITLE = "SoV measured basso"
DETAIL = (
    "Poche menzioni brand nei prompt probe. Rafforza entity, llms.txt e "
    "contenuti citabili; amplia il prompt bank."
)


def _fake_site():
    return SimpleNamespace(
        id=1,
        url="https://example.com",
        domain="example.com",
        aio_score=60,
        geo_score=55,
        pages_analyzed=3,
        crawl_pages=[],
        robots_probed_text="",
        competitors=[],
        signals={},
        findings=[
            {
                "severity": "warn",
                "title": TITLE,
                "detail": DETAIL,
            }
        ],
        updated_at=None,
        created_at=None,
    )


def _patch_site_query(monkeypatch, site):
    q = MagicMock()
    q.order_by.return_value.first.return_value = site
    monkeypatch.setattr(
        "services.geo_ui_payload.sites_query_for_user",
        lambda *_a, **_k: q,
    )
    monkeypatch.setattr(
        "services.geo_ui_payload.list_sov_snapshots",
        lambda *_a, **_k: [],
    )


def test_geo_ui_evidence_label_translated(monkeypatch):
    _patch_site_query(monkeypatch, _fake_site())
    monkeypatch.setattr(
        "services.geo_ui_payload.compute_engine_breakdown",
        lambda **_kw: {
            "engines": [],
            "brand_sov": 0,
            "label": "Misurato · 0 menzioni",
        },
    )
    user = SimpleNamespace(id=1, is_pro=False)

    with app.app_context():
        with force_locale("en"):
            payload = build_geo_ui_payload(
                user=user,
                SiteAnalysis=MagicMock(),
                SovSnapshot=MagicMock(),
            )

    assert payload["evidenceLabel"] == "Measured · 0 mentions"
    assert "Misurato" not in (payload["evidenceLabel"] or "")
    assert "menzioni" not in (payload["evidenceLabel"] or "")


def test_geo_ui_insights_translated_for_en(monkeypatch):
    _patch_site_query(monkeypatch, _fake_site())
    user = SimpleNamespace(id=1, is_pro=True)

    with app.app_context():
        with force_locale("en"):
            payload = build_geo_ui_payload(
                user=user,
                SiteAnalysis=MagicMock(),
                SovSnapshot=MagicMock(),
            )

    assert payload["ready"] is True
    assert payload["insights"], payload
    ins = payload["insights"][0]
    assert ins["severity"] == "warn"
    assert ins["severityLabel"] == "Warning"
    assert ins["title"] == "Low Measured SoV"
    assert "Few brand mentions" in ins["detail"]
    assert TITLE not in ins["title"]
    assert "Poche menzioni" not in ins["detail"]
    assert payload["ui"]["insightsTitle"] == "Actionable GEO Insights"
    assert "No critical/warn" in payload["ui"]["insightsEmpty"]


def test_geo_ui_insights_native_locales(monkeypatch):
    _patch_site_query(monkeypatch, _fake_site())
    user = SimpleNamespace(id=1, is_pro=True)

    expected_title = {
        "de": "Niedriger Measured SoV",
        "es": "SoV medido bajo",
        "ko": "측정 SoV 낮음",
        "zh_Hans": "实测 SoV 偏低",
    }
    expected_sev = {
        "de": "Warnung",
        "es": "Atención",
        "ko": "주의",
        "zh_Hans": "警告",
    }

    with app.app_context():
        for loc, want_title in expected_title.items():
            with force_locale(loc):
                payload = build_geo_ui_payload(
                    user=user,
                    SiteAnalysis=MagicMock(),
                    SovSnapshot=MagicMock(),
                )
            ins = payload["insights"][0]
            assert ins["title"] == want_title, (loc, ins["title"])
            assert ins["severityLabel"] == expected_sev[loc], (
                loc,
                ins["severityLabel"],
            )
            assert ins["detail"] != DETAIL, loc
