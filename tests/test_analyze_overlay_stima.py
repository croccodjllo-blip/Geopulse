"""Overlay must not flash-close onto the cost estimate; measured must not block remisure."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app import (
    AnalysisJob,
    SiteAnalysis,
    User,
    active_analyze_job_for_url,
    app,
    cancel_active_measured_for_analyze,
    db,
    ensure_schema,
)
from services.jobs import enqueue_analysis
from services.usage_billing import ConcurrentAnalysisError, assert_can_start_analysis


def test_overlay_js_opens_only_on_confirm_not_estimate_form():
    src = Path("static/js/analyze-overlay.js").read_text(encoding="utf-8")
    submit_handler = src.split('document.addEventListener("submit"', 1)[1]
    # Dashboard estimate composer must not open the crawl progress dialog.
    assert 'classList.contains("js-analyze-form")' not in submit_handler
    assert "js-analyze-confirm" in submit_handler
    assert "rememberPending" in submit_handler
    assert "Cost-estimate form" in src


def test_base_estimate_button_copy_not_analisi_in_corso():
    html = Path("templates/base.html").read_text(encoding="utf-8")
    assert "Preparazione stima" in html
    assert "isConfirm" in html
    assert "isEstimate" in html


def test_active_analyze_ignores_measured_by_default():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"overlay-meas-{uuid4().hex}@example.com",
            name="M",
            plan="plus",
            credit_balance_cents=5000,
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        url = f"https://overlay-{uuid4().hex}.example/"
        site = SiteAnalysis(
            user_id=user.id,
            url=url,
            domain="overlay.example",
            aio_score=50,
            geo_score=50,
        )
        db.session.add(site)
        db.session.commit()
        measured = AnalysisJob(
            user_id=user.id,
            url=url,
            status="running",
            source="measured",
            site_id=site.id,
            max_pages=4,
            run_measured=True,
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(measured)
        db.session.commit()

        assert active_analyze_job_for_url(user.id, url, site=site) is None
        assert (
            active_analyze_job_for_url(
                user.id, url, site=site, include_measured=True
            ).id
            == measured.id
        )


def test_cancel_measured_allows_new_crawl_enqueue():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"overlay-cancel-{uuid4().hex}@example.com",
            name="C",
            plan="plus",
            credit_balance_cents=5000,
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        url = f"https://cancel-{uuid4().hex}.example/"
        site = SiteAnalysis(
            user_id=user.id,
            url=url,
            domain="cancel.example",
            aio_score=40,
            geo_score=40,
        )
        db.session.add(site)
        db.session.commit()
        measured = AnalysisJob(
            user_id=user.id,
            url=url,
            status="running",
            source="measured",
            site_id=site.id,
            max_pages=4,
            held_cents=0,
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(measured)
        db.session.commit()

        n = cancel_active_measured_for_analyze(user, url, site=site)
        assert n == 1
        db.session.refresh(measured)
        assert measured.status == "error"
        assert "Sostituito" in (measured.error or "")

        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url=url,
            max_pages=4,
            active_check=lambda: active_analyze_job_for_url(user.id, url, site=site),
        )
        assert job.id != measured.id
        assert job.status == "pending"
        assert str(getattr(job, "source", "job")).lower() != "measured"


def test_concurrent_cap_ignores_measured_jobs():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"overlay-cap-{uuid4().hex}@example.com",
            name="Cap",
            plan="free",
            credit_balance_cents=5000,
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        measured = AnalysisJob(
            user_id=user.id,
            url="https://cap.example/",
            status="running",
            source="measured",
            max_pages=2,
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(measured)
        db.session.commit()
        # Free cap is 1 crawl job; a lone measured must not trip the cap.
        assert_can_start_analysis(
            db.session,
            user,
            AnalysisJob=AnalysisJob,
            required_cents=1,
            max_concurrent_jobs=1,
        )
        crawl = AnalysisJob(
            user_id=user.id,
            url="https://cap-crawl.example/",
            status="pending",
            source="job",
            max_pages=2,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(crawl)
        db.session.commit()
        with pytest.raises(ConcurrentAnalysisError):
            assert_can_start_analysis(
                db.session,
                user,
                AnalysisJob=AnalysisJob,
                required_cents=1,
                max_concurrent_jobs=1,
            )
