"""Dashboard signal-deck instruments are honest — no fabricated series."""

from __future__ import annotations

from pathlib import Path

from services.dash_charts import build_dash_charts
from services.engine_breakdown import compute_engine_breakdown

ROOT = Path(__file__).resolve().parents[1]
SIGNAL = (ROOT / "templates" / "partials" / "dash_signal.html").read_text(
    encoding="utf-8"
)
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")


def _breakdown():
    return compute_engine_breakdown(
        aio_score=62,
        geo_score=48,
        findings=[
            {"category": "aio", "severity": "critical", "title": "Title missing"},
            {"category": "geo", "severity": "warn", "title": "llms.txt weak"},
            {"category": "technical", "severity": "ok", "title": "HTTPS"},
        ],
        robots_text="User-agent: GPTBot\nAllow: /\n",
        competitors=[{"aio_score": 40, "geo_score": 30}],
    )


def test_signal_deck_is_wired_on_main_dashboard():
    assert 'include "partials/dash_signal.html"' in DASH
    assert "dash-signal" in SIGNAL
    assert "dash-spine" in SIGNAL
    assert "dash-orbit" in SIGNAL
    assert "dash-fault" in SIGNAL
    assert "dash-meridian" in SIGNAL
    assert "dash-kpis" in SIGNAL
    assert "dash-ring--" not in SIGNAL
    assert "dash-constellation" not in SIGNAL
    assert "dash-petals" not in SIGNAL
    assert 'style="' not in SIGNAL
    assert "style='" not in SIGNAL
    assert 'nonce="{{ csp_nonce }}"' in SIGNAL
    assert ".dash-signal" in CSS
    assert ".dash-orbit__sat" in CSS
    assert "#8B5CF6" not in CSS.split("Signal deck")[-1]


def test_build_charts_counts_real_findings_and_pages():
    charts = build_dash_charts(
        aio_score=62,
        geo_score=48,
        findings=[
            {"category": "aio", "severity": "critical", "title": "A"},
            {"category": "aio", "severity": "warn", "title": "B"},
            {"category": "geo", "severity": "ok", "title": "C"},
        ],
        crawl_pages=[
            {
                "url": "https://ex.com/a",
                "aio_score": 20,
                "geo_score": 80,
                "severity": "critical",
            },
            {
                "url": "https://ex.com/b",
                "aio_score": 70,
                "geo_score": 40,
                "severity": "ok",
            },
        ],
        geo_suite={
            "entity_graph": {"score": 55},
            "citability": {"score": 40},
            "schema_quality": {"score": 70},
            "publish_verify": {"score": 10},
            "llms_lint": {"score": 30},
            "locales": {"lang": "it", "hreflang": ["en"]},
        },
        engine_breakdown=_breakdown(),
        run_diff=None,
        sov_trend=[],
    )
    assert charts["aio"] == 62
    assert charts["geo"] == 48
    assert charts["mosaic"]["totals"]["critical"] == 1
    assert charts["mosaic"]["totals"]["warn"] == 1
    assert charts["mosaic"]["totals"]["ok"] == 1
    assert charts["field"]["n"] == 2
    assert charts["spark"] is None
    assert charts["delta"] is None
    assert len(charts["petals"]) == 6
    assert {p["id"] for p in charts["petals"]} >= {
        "entity_graph",
        "citability",
        "schema_quality",
    }
    assert charts["engines"]
    assert charts["radar"].get("points")
    assert charts["orbit"]["nodes"]
    assert charts["orbit"]["cx"] == 160.0
    for node in charts["orbit"]["nodes"]:
        assert "ox" in node and "oy" in node and "or" in node
        assert 0 <= node["ox"] <= 320
        assert 0 <= node["oy"] <= 200
    assert charts["meridian"]["n"] == 2
    assert charts["meridian"]["brand_x"] == 62
    assert {t["path"] for t in charts["meridian"]["ticks"]} >= {"/a", "/b"}


def test_spark_and_delta_only_when_real_history():
    empty = build_dash_charts(
        aio_score=10,
        geo_score=10,
        findings=[],
        crawl_pages=[],
        geo_suite={},
        engine_breakdown=None,
        run_diff={"has_previous": True, "delta_aio": None, "delta_geo": None},
        sov_trend=[{"rate": None}, {"rate": 20}],
    )
    assert empty["spark"] is None
    assert empty["delta"] is None
    assert empty["orbit"]["nodes"] == []

    live = build_dash_charts(
        aio_score=40,
        geo_score=50,
        findings=[],
        crawl_pages=[],
        geo_suite={},
        engine_breakdown=None,
        run_diff={"has_previous": True, "delta_aio": 3, "delta_geo": -2},
        sov_trend=[{"rate": 12}, {"rate": 18}, {"rate": 21}],
    )
    assert live["delta"] == {"aio": 3, "geo": -2}
    assert live["spark"] is not None
    assert live["spark"]["n"] == 3
    assert live["spark"]["first"] == 12
    assert live["spark"]["last"] == 21
    assert live["spark"]["delta"] == 9
    assert live["spark"]["points"]


def test_dashboard_renders_signal_instruments():
    import json
    from datetime import datetime, timezone
    from uuid import uuid4

    from app import SiteAnalysis, User, app, db, ensure_schema

    with app.app_context():
        ensure_schema()
        user = User(
            email=f"signal-{uuid4().hex}@example.com",
            name="Signal",
            plan="plus",
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("SignalDash!23456")
        db.session.add(user)
        db.session.commit()
        site = SiteAnalysis(
            user_id=user.id,
            url="https://signal.example/",
            domain="signal.example",
            aio_score=61,
            geo_score=47,
            findings_json=json.dumps(
                [
                    {"category": "aio", "severity": "critical", "title": "H1"},
                    {"category": "geo", "severity": "warn", "title": "Schema"},
                ]
            ),
            crawl_pages_json=json.dumps(
                {
                    "pages": [
                        {
                            "url": "https://signal.example/p",
                            "aio_score": 30,
                            "geo_score": 70,
                            "severity": "warn",
                        }
                    ]
                }
            ),
            updated_at=datetime.now(timezone.utc),
        )
        db.session.add(site)
        db.session.commit()
        uid, ver, site_id = user.id, int(user.session_version or 0), site.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["session_version"] = ver
    html = client.get(f"/dashboard?site={site_id}").get_data(as_text=True)
    assert "dash-signal" in html
    assert "dash-spine" in html
    assert "dash-orbit" in html
    assert "dash-fault" in html
    assert "dash-meridian" in html
    assert "dash-live-charts" in html
    assert "__CENTROPIC_GEO_COMPACT__" in html
    assert "dash-constellation" not in html
    assert "dash-ring--cvi" not in html
