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
    assert "dash-board" in SIGNAL
    assert "dash-tiles" in SIGNAL
    assert "dash-split" in SIGNAL
    assert "dash-pair--match" in SIGNAL
    assert "dash-split--wide" not in SIGNAL
    assert "dash-split__track" in SIGNAL
    assert "dash-rank" in SIGNAL
    assert "dash-hist" in SIGNAL
    assert "dash-fault" in SIGNAL
    assert "dash-kpis" in SIGNAL
    assert "dash-spine" not in SIGNAL
    assert "dash-orbit" not in SIGNAL
    assert "dash-meridian" not in SIGNAL
    assert "dash_geo_charts.html" not in SIGNAL
    assert "dash-ring--" not in SIGNAL
    assert "dash-constellation" not in SIGNAL
    assert "dash-petals" not in SIGNAL
    assert 'style="' not in SIGNAL
    assert "style='" not in SIGNAL
    assert 'nonce="{{ csp_nonce }}"' in SIGNAL
    assert ".dash-signal" in CSS
    assert ".dash-board" in CSS
    assert ".dash-hist" in CSS
    assert "dash-pair--match" in CSS
    assert "dash-split--wide" not in CSS
    assert "dash-split__track" in CSS
    assert "height: 10px" in CSS.split("dash-split__track")[1]
    assert "flex: 1 1 auto" in CSS.split("dash-area")[1]
    assert 'preserveAspectRatio="xMinYMid meet"' in SIGNAL
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
    assert charts["ranked"]
    assert charts["radar"].get("points")
    assert charts["split"]["total"] > 0
    assert charts["suite"]
    assert {row["id"] for row in charts["suite"]} >= {
        "entity_graph",
        "citability",
        "schema_quality",
    }
    assert charts["hist"]
    assert sum(b["n"] for b in charts["hist"]) == 2
    assert charts["pages"]["n"] == 2
    assert charts["pages"]["avg_aio"] == 45
    assert charts["pages"]["min_aio"] == 20
    assert charts["pages"]["max_aio"] == 70
    assert {row["path"] for row in charts["pages"]["rows"]} >= {"/a", "/b"}
    assert charts["orbit"]["nodes"]
    assert charts["meridian"]["n"] == 2


def test_history_trend_needs_two_scored_runs():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace

    from services.dash_charts import build_history_trend

    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    older = now - timedelta(days=4)
    one = [SimpleNamespace(aio_score=40, geo_score=30, created_at=now, domain="a.example")]
    assert build_history_trend(one) is None
    assert build_history_trend([]) is None

    two = [
        SimpleNamespace(aio_score=62, geo_score=48, created_at=now, domain="a.example"),
        SimpleNamespace(aio_score=50, geo_score=40, created_at=older, domain="a.example"),
    ]
    # Newest first, as dashboard_history queries.
    chart = build_history_trend(two)
    assert chart is not None
    assert chart["n"] == 2
    assert chart["first_aio"] == 50
    assert chart["last_aio"] == 62
    assert chart["delta_aio"] == 12
    assert chart["aio_line"]
    assert chart["geo_line"]
    assert [t["label"] for t in chart["ticks_x"]] == ["17/08", "21/08"]
    assert chart["latest_when"] == "21/08/2026 12:00"
    assert chart["rows"][-1]["when"] == "21/08/2026 12:00"
    assert chart["aio_marks"][-1]["latest"] is True

    many = [
        SimpleNamespace(
            aio_score=10 + i,
            geo_score=20 + i,
            created_at=now - timedelta(days=i),
            domain="a.example",
        )
        for i in range(20)
    ]
    capped = build_history_trend(many, limit=12)
    assert capped is not None
    assert capped["n"] == 12
    assert capped["last_aio"] == 10
    assert capped["first_aio"] == 21


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
    assert live["spark"]["area"]
    assert live["spark"]["line"]
    assert len(live["spark"]["marks"]) == 3


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
    assert "dash-board" in html
    assert "dash-tiles" in html
    assert "dash-split" in html
    assert "dash-pair--match" in html
    assert "dash-split--wide" not in html
    assert "dash-split__track" in html
    assert "dash-rank" in html
    assert "dash-hist" in html
    assert "dash-fault" in html
    assert "dash-pages" in html
    assert "dash-spine" not in html
    assert "dash-orbit" not in html
    assert "__CENTROPIC_GEO_COMPACT__" not in html
    assert "dash-live-charts" not in html
    assert "dash-constellation" not in html
    assert "dash-ring--cvi" not in html


def test_trend_history_is_scoped_to_selected_site():
    from datetime import datetime, timezone
    from uuid import uuid4

    from app import AnalysisRun, SiteAnalysis, User, app, db, ensure_schema

    with app.app_context():
        ensure_schema()
        user = User(
            email=f"trend-{uuid4().hex}@example.com",
            name="Trend",
            plan="plus",
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("TrendScope!23456")
        db.session.add(user)
        db.session.flush()
        keep = SiteAnalysis(
            user_id=user.id,
            url="https://keep.example/",
            domain="keep.example",
            aio_score=60,
            geo_score=50,
        )
        other = SiteAnalysis(
            user_id=user.id,
            url="https://other.example/",
            domain="other.example",
            aio_score=30,
            geo_score=20,
        )
        db.session.add_all([keep, other])
        db.session.flush()
        now = datetime.now(timezone.utc)
        db.session.add_all(
            [
                AnalysisRun(
                    site_id=keep.id,
                    user_id=user.id,
                    url=keep.url,
                    domain=keep.domain,
                    aio_score=60,
                    geo_score=50,
                    created_at=now,
                ),
                AnalysisRun(
                    site_id=other.id,
                    user_id=user.id,
                    url=other.url,
                    domain=other.domain,
                    aio_score=30,
                    geo_score=20,
                    created_at=now,
                ),
            ]
        )
        db.session.commit()
        uid, ver, keep_id = user.id, int(user.session_version or 0), keep.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["session_version"] = ver
    html = client.get(f"/dashboard/trend?site={keep_id}").get_data(as_text=True)
    assert "dash-trend__frame" in html
    list_at = html.find("history-list")
    assert list_at != -1
    listed = html[list_at:]
    assert "keep.example" in listed
    assert "other.example" not in listed
