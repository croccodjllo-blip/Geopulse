"""Failed-but-billed job refund + Free Edge CMS routes."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app import (
    AnalysisJob,
    CreditLedger,
    SiteAnalysis,
    User,
    app,
    db,
    ensure_schema,
)
from services.cms_connector import build_cms_bundle
from services.job_billing_recovery import (
    clear_paid_alert_settings,
    job_refund_idempotency_key,
    refund_failed_job_billing,
)
from services.usage_billing import topup_credit


def test_refund_failed_job_without_deliverable_is_idempotent():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"refund-{uuid4().hex}@example.com",
            name="Refund",
            plan="plus",
            credit_balance_cents=100,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        job = AnalysisJob(
            user_id=user.id,
            url=f"https://refund-{uuid4().hex}.example/",
            max_pages=2,
            status="error",
            billed_cents=40,
            held_cents=0,
            error="boom",
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(job)
        db.session.commit()

        first = refund_failed_job_billing(
            db.session,
            CreditLedger,
            user,
            job,
            SiteAnalysis=SiteAnalysis,
            topup_credit_fn=topup_credit,
        )
        db.session.commit()
        assert first == 40
        db.session.refresh(user)
        assert user.credit_balance_cents == 140
        key = job_refund_idempotency_key(job.id)
        assert CreditLedger.query.filter_by(stripe_payment_intent=key).count() == 1

        second = refund_failed_job_billing(
            db.session,
            CreditLedger,
            user,
            job,
            SiteAnalysis=SiteAnalysis,
            topup_credit_fn=topup_credit,
        )
        assert second == 0
        db.session.refresh(user)
        assert user.credit_balance_cents == 140


def test_refund_skipped_when_deliverable_exists():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"keep-{uuid4().hex}@example.com",
            name="Keep",
            plan="plus",
            credit_balance_cents=100,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        url = f"https://keep-{uuid4().hex}.example/"
        site = SiteAnalysis(
            user_id=user.id,
            url=url,
            domain="keep.example",
            aio_score=1,
            geo_score=1,
            findings_json="[]",
        )
        db.session.add(site)
        db.session.commit()
        job = AnalysisJob(
            user_id=user.id,
            url=url,
            max_pages=2,
            status="error",
            billed_cents=25,
            site_id=site.id,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(job)
        db.session.commit()
        refunded = refund_failed_job_billing(
            db.session,
            CreditLedger,
            user,
            job,
            SiteAnalysis=SiteAnalysis,
            topup_credit_fn=topup_credit,
        )
        assert refunded == 0
        db.session.refresh(user)
        assert user.credit_balance_cents == 100


def test_clear_paid_alert_settings():
    user = SimpleNamespace(
        alert_email_enabled=True,
        webhook_url="https://example.com/hook",
        webhook_secret="sec",
    )
    assert clear_paid_alert_settings(user) is True
    assert user.alert_email_enabled is False
    assert user.webhook_url is None
    assert user.webhook_secret is None


def test_cms_bundle_basic_omits_plus_routes():
    basic = build_cms_bundle(
        origin_edge_base="https://centropic.ai/e/tok",
        site_origin="https://example.com",
        full_edge=False,
    )
    assert basic["tier"] == "basic"
    assert "/llms.txt" in basic["routes"]
    assert "/robots.txt" not in basic["routes"]
    assert "/.well-known/organization.jsonld" not in basic["routes"]
    worker = basic["adapters"]["cloudflare"]["files"]["worker.js"]
    assert "/robots.txt" not in worker
    vercel = basic["adapters"]["vercel"]["files"]["vercel.json"]
    assert "/robots.txt" not in vercel

    full = build_cms_bundle(
        origin_edge_base="https://centropic.ai/e/tok",
        site_origin="https://example.com",
        full_edge=True,
    )
    assert full["tier"] == "full"
    assert "/robots.txt" in full["routes"]
