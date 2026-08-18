"""Confirm start must keep the progress overlay (AJAX enqueue + recent-done race)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app import (
    AnalysisJob,
    SiteAnalysis,
    User,
    app,
    db,
    ensure_schema,
    resolve_analyze_overlay_job,
)


def test_overlay_js_confirm_uses_fetch_not_full_navigation():
    src = Path("static/js/analyze-overlay.js").read_text(encoding="utf-8")
    assert "ev.preventDefault()" in src
    assert 'Accept: "application/json"' in src
    assert "X-Requested-With" in src
    assert "api._startPoll" in src
    assert 'fd.set("ajax", "1")' in src


def test_resolve_overlay_job_includes_fresh_done_crawl():
    now = datetime.now(timezone.utc)
    running = SimpleNamespace(
        status="running", source="job", finished_at=None, id=1
    )
    assert resolve_analyze_overlay_job(running) is running

    fresh = SimpleNamespace(
        status="done",
        source="job",
        finished_at=now - timedelta(seconds=30),
        id=2,
    )
    assert resolve_analyze_overlay_job(fresh) is fresh

    stale = SimpleNamespace(
        status="done",
        source="job",
        finished_at=now - timedelta(minutes=10),
        id=3,
    )
    assert resolve_analyze_overlay_job(stale) is None

    measured = SimpleNamespace(
        status="done",
        source="measured",
        finished_at=now - timedelta(seconds=10),
        id=4,
    )
    assert resolve_analyze_overlay_job(measured) is None


def test_confirm_enqueue_returns_json_for_ajax(monkeypatch):
    monkeypatch.setenv("ASYNC_ANALYZE", "1")
    import app as app_mod

    monkeypatch.setattr(app_mod, "ASYNC_ANALYZE", True)

    class _Preflight:
        is_giant = False
        required_cost_cents = 25
        message = ""

    monkeypatch.setattr(
        app_mod,
        "normalize_url",
        lambda u: u if u.startswith("http") else "https://" + u,
    )
    monkeypatch.setattr(
        app_mod,
        "check_page_word_budget",
        lambda **kwargs: _Preflight(),
    )
    monkeypatch.setattr(
        app_mod,
        "estimate_analysis_cost",
        lambda **kwargs: SimpleNamespace(
            service_cost_eur_cents=25,
            breakdown=[],
        ),
    )
    monkeypatch.setattr(app_mod, "kick_analyze_worker", lambda: None)
    monkeypatch.setattr(
        "services.jobs._begin_immediate",
        lambda db_session: None,
    )
    # hold_credit may also begin immediate
    monkeypatch.setattr(
        "services.usage_billing._begin_immediate",
        lambda db_session: None,
    )

    with app.app_context():
        ensure_schema()
        app.config["WTF_CSRF_ENABLED"] = False
        user = User(
            email=f"ajax-confirm-{uuid4().hex}@example.com",
            name="Ajax",
            plan="plus",
            credit_balance_cents=50_000,
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        url = f"https://ajax-{uuid4().hex}.example/"
        site = SiteAnalysis(
            user_id=user.id,
            url=url,
            domain="ajax.example",
            aio_score=55,
            geo_score=55,
        )
        db.session.add(site)
        db.session.commit()

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["session_version"] = int(getattr(user, "session_version", 0) or 0)

        resp = client.post(
            "/dashboard/analyze/confirmed",
            data={
                "url": url,
                "run_measured": "0",
                "competitors": "",
                "deep_crawl": "0",
                "cost_cents": "1",
                "ajax": "1",
            },
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
        data = resp.get_json()
        assert data["ok"] is True
        assert data["job_id"]
        assert data["status_url"]
        assert "/dashboard/jobs/" in data["status_url"]
        job = db.session.get(AnalysisJob, data["job_id"])
        assert job is not None
        assert job.status in {"pending", "running"}
        assert str(getattr(job, "source", "job")).lower() != "measured"


def test_dashboard_auto_opens_for_fresh_done_job():
    with app.app_context():
        ensure_schema()
        now = datetime.now(timezone.utc)
        user = User(
            email=f"fresh-done-{uuid4().hex}@example.com",
            name="F",
            plan="plus",
            credit_balance_cents=5000,
            email_verified_at=now,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        site = SiteAnalysis(
            user_id=user.id,
            url="https://fresh-done.example/",
            domain="fresh-done.example",
            aio_score=70,
            geo_score=70,
            updated_at=now,
            created_at=now,
        )
        db.session.add(site)
        db.session.commit()
        job = AnalysisJob(
            user_id=user.id,
            url=site.url,
            status="done",
            source="job",
            site_id=site.id,
            max_pages=8,
            finished_at=now - timedelta(seconds=20),
            created_at=now - timedelta(seconds=40),
        )
        db.session.add(job)
        db.session.commit()

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["session_version"] = int(getattr(user, "session_version", 0) or 0)
        resp = client.get(f"/dashboard?job={job.id}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'data-auto-open="1"' in html
        assert f"/dashboard/jobs/{job.id}" in html
