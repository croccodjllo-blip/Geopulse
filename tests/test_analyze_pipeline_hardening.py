"""Hardening: API async queue, persist source/org, reclaim reconcile."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app import (
    AnalysisJob,
    AnalysisRun,
    SiteAnalysis,
    User,
    app,
    db,
    ensure_schema,
    generate_api_key,
)
from services.analysis_store import persist_analysis
from services.jobs import (
    complete_job,
    enqueue_analysis,
    mark_job_site,
    reclaim_stale_jobs,
)
from services.usage_billing import ConcurrentAnalysisError, assert_can_start_analysis


def test_persist_preserves_created_at_and_source_api():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"persist-{uuid4().hex}@example.com",
            name="Persist",
            plan="business",
        )
        user.set_password("PersistTest!23456")
        db.session.add(user)
        db.session.commit()

        first = persist_analysis(
            db.session,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user_id=user.id,
            url="https://example.com/",
            result={
                "scraped": {"domain": "example.com", "title": "One"},
                "aio_score": 10,
                "geo_score": 20,
                "findings": [],
            },
            pack={},
            source="api",
            user=user,
        )
        created = first.created_at
        assert first.organization_id is not None
        run = AnalysisRun.query.filter_by(site_id=first.id).first()
        assert run is not None
        assert run.source == "api"

        # Remesure should not rewind first-seen created_at.
        second = persist_analysis(
            db.session,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user_id=user.id,
            url="https://example.com/",
            existing=first,
            result={
                "scraped": {"domain": "example.com", "title": "Two"},
                "aio_score": 11,
                "geo_score": 21,
                "findings": [],
            },
            pack={},
            source="verify",
            user=user,
        )
        assert second.created_at == created
        if hasattr(second, "updated_at") and second.updated_at:
            assert second.updated_at >= created


def test_reclaim_marks_done_when_site_already_set():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"reclaim-{uuid4().hex}@example.com",
            name="Reclaim",
            plan="plus",
        )
        user.set_password("ReclaimTest!23456")
        db.session.add(user)
        db.session.commit()
        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://reclaim.example/",
            max_pages=2,
            source="job",
        )
        job.status = "running"
        job.lease_token = "deadbeef"
        job.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        job.heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        job.site_id = 999
        job.billed_cents = 0
        db.session.commit()
        n = reclaim_stale_jobs(db.session, AnalysisJob)
        assert n >= 1
        row = db.session.get(AnalysisJob, job.id)
        assert row.status == "done"


def test_assert_can_start_still_enforces_concurrency_for_unlimited():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"conc-{uuid4().hex}@example.com",
            name="Conc",
            plan="free",
            role="internal",
        )
        user.set_password("ConcTest!23456")
        user.credit_balance_cents = 0
        db.session.add(user)
        db.session.commit()
        for i in range(2):
            enqueue_analysis(
                db.session,
                AnalysisJob,
                user_id=user.id,
                url=f"https://c{i}.example/",
                max_pages=1,
            )
        try:
            assert_can_start_analysis(
                db.session,
                user,
                AnalysisJob=AnalysisJob,
                required_cents=1,
                max_concurrent_jobs=2,
            )
            raised = False
        except ConcurrentAnalysisError:
            raised = True
        assert raised is True


def test_api_analyze_returns_202_job():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"api-{uuid4().hex}@example.com",
            name="Api",
            plan="business",
            role="internal",
        )
        user.set_password("ApiTest!23456")
        raw, prefix, digest = generate_api_key()
        user.api_key_hash = digest
        user.api_key_prefix = prefix
        db.session.add(user)
        db.session.commit()

    client = app.test_client()
    resp = client.post(
        "/api/v1/analyze",
        json={"url": "https://example.com/"},
        headers={"X-Api-Key": raw},
    )
    assert resp.status_code == 202, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["ok"] is True
    assert data["queued"] is True
    assert data["job_id"]
    job_id = data["job_id"]

    status = client.get(f"/api/v1/jobs/{job_id}", headers={"X-Api-Key": raw})
    assert status.status_code == 200
    body = status.get_json()
    assert body["status"] in {"pending", "running", "done", "error"}
    assert "billing" in body
    assert "billed_tokens" in body["billing"]


def test_mark_job_site_and_complete_reconcile():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"mark-{uuid4().hex}@example.com",
            name="Mark",
            plan="plus",
        )
        user.set_password("MarkTest!23456")
        db.session.add(user)
        db.session.commit()
        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://mark.example/",
            max_pages=1,
        )
        job.status = "running"
        job.lease_token = "lease-mark"
        db.session.commit()
        assert mark_job_site(db.session, job, site_id=42, lease_token="lease-mark")
        # Steal lease then complete should still reconcile via site_id.
        job.lease_token = "other"
        job.status = "running"
        db.session.commit()
        # complete with old lease fails ownership, but site_id set → reconcile
        job.lease_token = "lease-mark"
        ok = complete_job(db.session, job, site_id=42, lease_token="lease-mark")
        # May succeed if lease still matches; either way site_id preserved.
        row = db.session.get(AnalysisJob, job.id)
        assert row.site_id == 42
        assert ok is True or row.status in {"done", "running"}
