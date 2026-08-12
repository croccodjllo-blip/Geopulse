"""Dashboard must show the just-finished analysis, not a stale sibling report."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import AnalysisJob, SiteAnalysis, User, app, db, ensure_schema
from services.jobs import claim_next_job, complete_job, enqueue_analysis, mark_job_site


def test_complete_job_does_not_wipe_site_id_when_none():
    with app.app_context():
        ensure_schema()
        u = User(
            email="fresh-siteid@example.com",
            name="F",
            plan="plus",
            email_verified_at=datetime.now(timezone.utc),
        )
        u.set_password("x" * 12)
        db.session.add(u)
        db.session.commit()
        site = SiteAnalysis(
            user_id=u.id,
            url="https://example.com/fresh",
            domain="example.com",
            aio_score=50,
            geo_score=50,
        )
        db.session.add(site)
        db.session.commit()
        enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=u.id,
            url=site.url,
            max_pages=2,
        )
        claimed = claim_next_job(db.session, AnalysisJob)
        assert claimed is not None
        assert mark_job_site(
            db.session, claimed, site_id=site.id, lease_token=claimed.lease_token
        )
        assert complete_job(
            db.session, claimed, site_id=None, lease_token=claimed.lease_token
        )
        db.session.refresh(claimed)
        assert claimed.status == "done"
        assert claimed.site_id == site.id


def test_overlay_js_pins_site_and_job_on_done():
    src = Path("static/js/analyze-overlay.js").read_text(encoding="utf-8")
    assert 'site=" + encodeURIComponent(String(data.site_id))' in src
    assert 'job=" + encodeURIComponent(String(data.id))' in src
    assert "location.replace" in src


def test_dashboard_does_not_auto_open_overlay_for_measured_followup():
    """After crawl completes, deferred measured must not block the UI overlay."""
    with app.app_context():
        ensure_schema()
        now = datetime.now(timezone.utc)
        user = User(
            email="fresh-measured-overlay@example.com",
            name="M",
            plan="plus",
            email_verified_at=now,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        site = SiteAnalysis(
            user_id=user.id,
            url="https://nike.example/",
            domain="nike.example",
            aio_score=66,
            geo_score=70,
            page_title="Nike",
            created_at=now,
            updated_at=now,
        )
        db.session.add(site)
        db.session.commit()
        measured = AnalysisJob(
            user_id=user.id,
            url=site.url,
            status="running",
            source="measured",
            site_id=site.id,
            max_pages=8,
            run_measured=True,
            started_at=now,
            created_at=now,
            heartbeat_at=now,
            progress_phase="sov",
            progress_done=0,
            progress_total=1,
        )
        db.session.add(measured)
        db.session.commit()

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["session_version"] = int(getattr(user, "session_version", 0) or 0)
        resp = client.get(f"/dashboard?site={site.id}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "nike.example" in html
        assert 'data-auto-open="1"' not in html
        assert "SoV measured in aggiornamento" in html


def test_dashboard_report_uses_updated_at_not_created_at():
    with app.app_context():
        ensure_schema()
        now = datetime.now(timezone.utc)
        user = User(
            email="fresh-dash@example.com",
            name="D",
            plan="plus",
            email_verified_at=now,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()

        stale_sibling = SiteAnalysis(
            user_id=user.id,
            url="https://old.example/",
            domain="old.example",
            aio_score=10,
            geo_score=10,
            page_title="Old",
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
        )
        reanalyzed = SiteAnalysis(
            user_id=user.id,
            url="https://fresh.example/",
            domain="fresh.example",
            aio_score=88,
            geo_score=77,
            page_title="Fresh Title",
            created_at=now - timedelta(days=30),
            updated_at=now,
        )
        db.session.add_all([stale_sibling, reanalyzed])
        db.session.commit()

        job = AnalysisJob(
            user_id=user.id,
            url=reanalyzed.url,
            status="done",
            site_id=reanalyzed.id,
            max_pages=4,
            finished_at=now,
            created_at=now - timedelta(minutes=2),
        )
        db.session.add(job)
        db.session.commit()

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["session_version"] = int(getattr(user, "session_version", 0) or 0)

        resp = client.get("/dashboard")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "fresh.example" in html
        assert "Fresh Title" in html
        # Must surface last-analysis time (updated_at), not first-seen created_at.
        assert now.strftime("%d/%m/%Y %H:%M") in html
        assert (now - timedelta(days=30)).strftime("%d/%m/%Y %H:%M") not in html
        assert resp.headers.get("Cache-Control", "").startswith("private, no-store")
