from __future__ import annotations

from datetime import datetime, timezone

from app import AnalysisJob, User, app, db, ensure_schema
from services.jobs import claim_next_job, enqueue_analysis


def test_claim_next_job_is_exclusive():
    with app.app_context():
        ensure_schema()
        # DB in-memory: create user + two pending jobs
        user = User(email="claim-test@example.com", name="T", plan="plus")
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()

        j1 = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://example.com/a",
            max_pages=2,
        )
        j2 = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://example.com/b",
            max_pages=2,
        )
        assert j1.id != j2.id

        c1 = claim_next_job(db.session, AnalysisJob)
        c2 = claim_next_job(db.session, AnalysisJob)
        c3 = claim_next_job(db.session, AnalysisJob)

        assert c1 is not None and c1.status == "running"
        assert c2 is not None and c2.status == "running"
        assert {c1.id, c2.id} == {j1.id, j2.id}
        assert c3 is None

        # Simula race: forza un job pending e due claim sullo stesso id via update condizionale
        j1.status = "pending"
        j1.started_at = None
        db.session.commit()
        # Solo un update dovrebbe vincere se richiamiamo claim due volte sequenzialmente
        won = claim_next_job(db.session, AnalysisJob)
        assert won is not None
        assert won.id == j1.id
        assert claim_next_job(db.session, AnalysisJob) is None


def test_reclaim_stale_running_jobs():
    from datetime import timedelta

    from services.jobs import reclaim_stale_jobs

    with app.app_context():
        ensure_schema()
        user = User(email="stale-test@example.com", name="S", plan="plus")
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://example.com/stale",
            max_pages=2,
        )
        job.status = "running"
        job.started_at = datetime.now(timezone.utc) - timedelta(minutes=40)
        db.session.commit()

        n = reclaim_stale_jobs(db.session, AnalysisJob, older_than_minutes=25)
        assert n == 1
        db.session.refresh(job)
        assert job.status == "pending"
        assert job.started_at is None
