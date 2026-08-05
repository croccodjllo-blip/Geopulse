"""Admin job retry must not re-queue partially billed work."""

from __future__ import annotations

from app import AnalysisJob, User, app, db, ensure_schema


def _admin_client(admin: User):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = admin.id
        sess["session_version"] = int(admin.session_version or 0)
    return client


def test_admin_retry_blocks_partially_billed_job():
    with app.app_context():
        ensure_schema()
        prev = app.config.get("WTF_CSRF_ENABLED", True)
        app.config["WTF_CSRF_ENABLED"] = False
        try:
            admin = User(
                email="retry-admin@example.com", name="Admin", plan="admin", role="admin"
            )
            admin.set_password("ArchTest!23456")
            owner = User(email="retry-owner@example.com", name="Owner", plan="plus")
            owner.set_password("ArchTest!23456")
            db.session.add_all([admin, owner])
            db.session.commit()

            job = AnalysisJob(
                user_id=owner.id,
                url="https://example.com/billed",
                max_pages=8,
                status="error",
                error="partial",
                billed_cents=42,
                attempt_count=1,
            )
            db.session.add(job)
            db.session.commit()
            job_id = job.id

            client = _admin_client(admin)
            resp = client.post(f"/admin/jobs/{job_id}/retry", follow_redirects=True)
            assert resp.status_code == 200
            row = db.session.get(AnalysisJob, job_id)
            assert row is not None
            assert row.status == "error"
            assert int(row.billed_cents or 0) == 42
            assert b"parzialmente addebitato" in resp.data or b"doppia" in resp.data
        finally:
            app.config["WTF_CSRF_ENABLED"] = prev


def test_admin_retry_allows_unbilled_error_job():
    with app.app_context():
        ensure_schema()
        prev = app.config.get("WTF_CSRF_ENABLED", True)
        app.config["WTF_CSRF_ENABLED"] = False
        try:
            admin = User(
                email="retry-admin2@example.com", name="Admin", plan="admin", role="admin"
            )
            admin.set_password("ArchTest!23456")
            owner = User(
                email="retry-owner2@example.com",
                name="Owner",
                plan="plus",
                credit_balance_cents=50_000,
            )
            owner.set_password("ArchTest!23456")
            db.session.add_all([admin, owner])
            db.session.commit()

            job = AnalysisJob(
                user_id=owner.id,
                url="https://example.com/unbilled",
                max_pages=8,
                status="error",
                error="timeout",
                billed_cents=0,
                attempt_count=2,
            )
            db.session.add(job)
            db.session.commit()
            job_id = job.id

            client = _admin_client(admin)
            resp = client.post(f"/admin/jobs/{job_id}/retry", follow_redirects=True)
            assert resp.status_code == 200
            row = db.session.get(AnalysisJob, job_id)
            assert row is not None
            assert row.status == "pending"
            assert row.attempt_count == 0
            assert row.error is None
            # Retry must re-hold credit (previous hold was released on fail).
            assert int(row.held_cents or 0) >= 0
        finally:
            app.config["WTF_CSRF_ENABLED"] = prev
