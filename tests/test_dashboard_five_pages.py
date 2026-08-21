"""Workspace IA: five pages, full width, no left dock."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPBAR = (ROOT / "templates" / "partials" / "app_topbar.html").read_text(
    encoding="utf-8"
)
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
PROMPT = (ROOT / "templates" / "dashboard_prompt.html").read_text(encoding="utf-8")
BENCH = (ROOT / "templates" / "dashboard_benchmark.html").read_text(encoding="utf-8")
TREND = (ROOT / "templates" / "dashboard_trend.html").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")


def test_topbar_has_exactly_five_pages():
    assert "{{ _('Panoramica') }}" in TOPBAR
    assert "{{ _('Benchmark') }}" in TOPBAR
    assert "{{ _('Prompt') }}" in TOPBAR
    assert "{{ _('Trend') }}" in TOPBAR
    assert "{{ _('Guida') }}" in TOPBAR
    assert "{{ _('Share of Voice') }}" not in TOPBAR
    assert "{{ _('Dashboard') }}" not in TOPBAR
    assert "{{ _('Impostazioni') }}" in TOPBAR  # avatar aria-label
    assert "dashboard_settings" in TOPBAR


def test_routes_registered():
    assert 'def dashboard_benchmark(' in APP
    assert '"/dashboard/benchmark"' in APP
    assert 'def dashboard_prompt(' in APP
    assert '"/dashboard/prompt"' in APP
    assert 'def dashboard_trend(' in APP
    assert '"/dashboard/trend"' in APP


def test_panoramica_is_charts_only():
    assert "dash_signal.html" in DASH
    assert "dash-kpis" in (ROOT / "templates" / "partials" / "dash_signal.html").read_text(
        encoding="utf-8"
    )
    assert "dash_audit.html" in DASH
    assert "dash-compose" in (ROOT / "templates" / "partials" / "dash_audit.html").read_text(
        encoding="utf-8"
    )
    assert "dash-board" in (
        ROOT / "templates" / "partials" / "dash_signal.html"
    ).read_text(encoding="utf-8")
    assert "dash-hist" in (
        ROOT / "templates" / "partials" / "dash_signal.html"
    ).read_text(encoding="utf-8")
    assert "dash_geo_charts.html" not in (
        ROOT / "templates" / "partials" / "dash_signal.html"
    ).read_text(encoding="utf-8")
    assert "Compositore" not in DASH
    assert "{{ _('Audit') }}" in (ROOT / "templates" / "partials" / "dash_audit.html").read_text(
        encoding="utf-8"
    )
    assert "pack-deliverable" not in DASH
    assert "comp-arena" not in DASH
    assert "id=\"findings\"" not in DASH


def test_prompt_has_findings_and_pack():
    assert "dash-findings" in PROMPT
    assert "dash_prompt_ops.html" in PROMPT
    ops = (ROOT / "templates" / "partials" / "dash_prompt_ops.html").read_text(
        encoding="utf-8"
    )
    assert "id=\"pack\"" in ops
    assert "id=\"edge-signals\"" in ops
    assert "download_pack" in ops


def test_benchmark_uses_competitor_snapshot():
    assert "competitor_snapshot.html" in BENCH


def test_trend_has_history_and_charts():
    assert "history-list" in TREND
    assert "dash-spark" in TREND
    assert "diff-strip" in TREND


def test_full_width_workspace():
    assert "max-width: none !important" in CSS
    assert "height: 100dvh" in CSS
    assert "max-height: 100dvh" in CSS
    assert "workspace--fill" in CSS
    assert ".dash-kpis" in CSS
    assert ".dash-board" in CSS
    assert ".dash-wide" in CSS
    assert ".dash-prompt" in CSS
    assert 'class="workspace workspace--fill"' in DASH


def test_five_pages_render_for_plus_user():
    import json
    from datetime import datetime, timezone
    from uuid import uuid4

    from app import AnalysisRun, SiteAnalysis, User, app, db, ensure_schema

    with app.app_context():
        ensure_schema()
        user = User(
            email=f"five-{uuid4().hex}@example.com",
            name="Five",
            plan="plus",
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("FivePages!23456")
        db.session.add(user)
        db.session.commit()
        site = SiteAnalysis(
            user_id=user.id,
            url="https://five.example/",
            domain="five.example",
            aio_score=58,
            geo_score=44,
            findings_json=json.dumps(
                [{"category": "aio", "severity": "critical", "title": "H1"}]
            ),
            crawl_pages_json=json.dumps(
                {
                    "pages": [],
                    "competitors": [
                        {"domain": "rival.example", "aio_score": 40, "geo_score": 30}
                    ],
                }
            ),
            updated_at=datetime.now(timezone.utc),
        )
        db.session.add(site)
        db.session.flush()
        db.session.add(
            AnalysisRun(
                site_id=site.id,
                user_id=user.id,
                url=site.url,
                domain=site.domain,
                aio_score=58,
                geo_score=44,
                findings_json=site.findings_json,
            )
        )
        db.session.commit()
        uid, ver, site_id = user.id, int(user.session_version or 0), site.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["session_version"] = ver

    overview = client.get(f"/dashboard?site={site_id}").get_data(as_text=True)
    assert "app-topbar__pills" in overview
    assert "dash-kpis" in overview
    assert "dash-board" in overview
    assert "dash-split" in overview
    assert "dash-rank" in overview
    assert "__CENTROPIC_GEO_COMPACT__" not in overview
    assert "dash-audit" in overview
    assert ">Audit<" in overview
    assert "Compositore" not in overview
    assert "Apri grafici interattivi" not in overview
    assert "Nuova analisi" not in overview
    assert 'id="pack"' not in overview
    assert "comp-arena" not in overview

    bench = client.get(f"/dashboard/benchmark?site={site_id}").get_data(as_text=True)
    assert "comp-arena" in bench
    assert "Vs competitor" in bench or "Δ AIO" in bench

    prompt = client.get(f"/dashboard/prompt?site={site_id}").get_data(as_text=True)
    assert 'id="findings"' in prompt
    assert 'id="pack"' in prompt

    trend = client.get(f"/dashboard/trend?site={site_id}").get_data(as_text=True)
    assert "history-list" in trend

    guide = client.get("/dashboard/guida").get_data(as_text=True)
    assert "guide-page" in guide
