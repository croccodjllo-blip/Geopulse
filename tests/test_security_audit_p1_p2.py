"""Fail-closed security audit: Paddle bind, preview claim, ACL, catalog."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app import (
    AnalysisJob,
    AnalysisRun,
    GuestPreview,
    SiteAnalysis,
    User,
    app,
    db,
    ensure_schema,
    generate_api_key,
)
from centropic.tenancy import OrganizationMember, ensure_personal_org
from services.alerts import _user_may_dispatch_alerts, emit_signed_webhook
from services.paddle_billing import (
    assert_transaction_matches_catalog,
    claim_webhook_event_once,
    issue_checkout_bind,
    resolve_webhook_user,
    verify_checkout_bind,
)
from services.preview_analyze import claim_guest_preview
from services.webhook_crypto import (
    reset_webhook_crypto_for_tests,
    seal_webhook_secret,
)


def test_checkout_bind_roundtrip_and_expiry(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-key-not-for-prod")
    now = 1_700_000_000
    bind = issue_checkout_bind(42, now=now)
    assert verify_checkout_bind(42, bind, now=now) is True
    assert verify_checkout_bind(99, bind, now=now) is False
    assert verify_checkout_bind(42, {"centropic_user_id": "42"}, now=now) is False
    stale = {**bind, "bind_ts": str(now - 10_000)}
    assert verify_checkout_bind(42, stale, now=now, max_age=3600) is False


def test_first_bind_requires_valid_sig_not_victim_uid():
    victim = SimpleNamespace(id=10, paddle_customer_id=None, paddle_subscription_id=None)
    attacker = SimpleNamespace(id=20, paddle_customer_id=None, paddle_subscription_id=None)
    users = {10: victim, 20: attacker}
    forged = resolve_webhook_user(
        {
            "customer_id": "ctm_new",
            "custom_data": {"centropic_user_id": "10"},
        },
        by_customer_id=lambda cid: None,
        by_subscription_id=lambda sid: None,
        by_user_id=lambda uid: users.get(uid),
        customer_taken_by_other=lambda cid, uid: None,
    )
    assert forged is None
    bind = issue_checkout_bind(10)
    legit = resolve_webhook_user(
        {
            "customer_id": "ctm_new",
            "custom_data": {"centropic_user_id": "10", **bind},
        },
        by_customer_id=lambda cid: None,
        by_subscription_id=lambda sid: None,
        by_user_id=lambda uid: users.get(uid),
        customer_taken_by_other=lambda cid, uid: None,
    )
    assert legit is victim


def test_catalog_assert_fail_closed_when_amount_missing():
    err = assert_transaction_matches_catalog({"id": "txn_x"}, product="plus")
    assert err and "catalog_amount_unavailable" in err


def test_claim_webhook_event_once_redis_nx(monkeypatch):
    store: dict[str, str] = {}

    class _R:
        def set(self, key, value, nx=False, ex=None):
            if nx and key in store:
                return False
            store[key] = value
            return True

    monkeypatch.setattr("services.redis_client.get_redis", lambda ping=False: _R())
    assert claim_webhook_event_once("evt_1") is True
    assert claim_webhook_event_once("evt_1") is False
    assert claim_webhook_event_once("") is True


def test_past_due_user_cannot_dispatch_alerts():
    expired = SimpleNamespace(
        id=1,
        is_admin=False,
        is_pro=False,
        is_business=False,
        plan="plus",
        paddle_past_due_since=datetime.now(timezone.utc) - timedelta(days=10),
    )
    assert _user_may_dispatch_alerts(expired) is False
    plus = SimpleNamespace(
        id=2,
        is_admin=False,
        is_pro=True,
        is_business=False,
        plan="plus",
        paddle_past_due_since=None,
    )
    assert _user_may_dispatch_alerts(plus) is True


def test_emit_skips_unsigned_when_reveal_fails(monkeypatch):
    reset_webhook_crypto_for_tests()
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-flask-secret-for-webhook-crypto")
    reset_webhook_crypto_for_tests()
    sealed = seal_webhook_secret("hook-sekrit")
    user = SimpleNamespace(
        id=3,
        is_admin=False,
        is_pro=True,
        plan="plus",
        webhook_url="https://hooks.example.com/h",
        webhook_secret=sealed,
        paddle_past_due_since=None,
    )
    posted: list[dict] = []

    def _deliver(**kwargs):
        posted.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr("services.alerts.deliver_webhook", _deliver)
    monkeypatch.setattr(
        "services.webhook_crypto.reveal_webhook_secret", lambda _stored: ""
    )
    out = emit_signed_webhook(
        user=user,
        site=SimpleNamespace(id=1, url="https://ex.com/", domain="ex.com"),
        payload={"event": "analysis.completed"},
    )
    assert out["ok"] is False
    assert out["error"] == "secret_unavailable"
    assert posted == []
    reset_webhook_crypto_for_tests()


def test_establish_session_keeps_guest_preview_token():
    from app import _establish_session

    with app.app_context():
        ensure_schema()
        user = User(
            email=f"sess-prev-{uuid4().hex}@example.com",
            name="Sess",
            plan="free",
        )
        user.set_password("SessPrev!23456")
        user.email_verified_at = datetime.now(timezone.utc)
        db.session.add(user)
        db.session.commit()
        with app.test_request_context("/"):
            from flask import session as flask_session

            flask_session["guest_preview_token"] = "keep-me-token"
            _establish_session(user)
            assert flask_session.get("guest_preview_token") == "keep-me-token"
            assert flask_session.get("user_id") == user.id


def test_anteprima_auto_claim_requires_session_token():
    with app.app_context():
        ensure_schema()
        owner = User(
            email=f"claim-own-{uuid4().hex}@example.com",
            name="Owner",
            plan="free",
        )
        owner.set_password("ClaimOwn!23456")
        owner.email_verified_at = datetime.now(timezone.utc)
        hijacker = User(
            email=f"claim-hij-{uuid4().hex}@example.com",
            name="Hijack",
            plan="free",
        )
        hijacker.set_password("ClaimHij!23456")
        hijacker.email_verified_at = datetime.now(timezone.utc)
        db.session.add_all([owner, hijacker])
        db.session.commit()
        tok = f"prev-{uuid4().hex[:12]}"
        preview = GuestPreview(
            token=tok,
            url="https://claim-acl.example/",
            domain="claim-acl.example",
            status="done",
            aio_score=40,
            geo_score=42,
            findings_json="[]",
            result_json=json.dumps(
                {
                    "scraped": {"domain": "claim-acl.example", "title": "Demo"},
                    "aio_score": 40,
                    "geo_score": 42,
                    "findings": [],
                }
            ),
            pack_json=json.dumps({"llms.txt": "# claimed"}),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.session.add(preview)
        db.session.commit()
        hijacker_id = hijacker.id
        hijacker_ver = int(getattr(hijacker, "session_version", 0) or 0)
        preview_id = preview.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = hijacker_id
        sess["session_version"] = hijacker_ver
        # No matching guest_preview_token.
    resp = client.get(f"/anteprima/{tok}", follow_redirects=False)
    assert resp.status_code == 200
    with app.app_context():
        row = db.session.get(GuestPreview, preview_id)
        assert row.claimed_user_id is None


def test_claim_guest_preview_second_user_loses():
    with app.app_context():
        ensure_schema()
        first = User(
            email=f"claim-a-{uuid4().hex}@example.com",
            name="A",
            plan="free",
        )
        first.set_password("ClaimA!23456")
        second = User(
            email=f"claim-b-{uuid4().hex}@example.com",
            name="B",
            plan="free",
        )
        second.set_password("ClaimB!23456")
        db.session.add_all([first, second])
        db.session.commit()
        preview = GuestPreview(
            token=f"race-{uuid4().hex[:10]}",
            url="https://race-demo.example/",
            domain="race-demo.example",
            status="done",
            aio_score=40,
            geo_score=42,
            findings_json="[]",
            result_json=json.dumps(
                {
                    "scraped": {"domain": "race-demo.example", "title": "Demo"},
                    "aio_score": 40,
                    "geo_score": 42,
                    "findings": [],
                }
            ),
            pack_json=json.dumps({"llms.txt": "# claimed"}),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.session.add(preview)
        db.session.commit()
        site = claim_guest_preview(
            db_session=db.session,
            GuestPreview=GuestPreview,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user=first,
            token=preview.token,
        )
        assert site is not None
        lost = claim_guest_preview(
            db_session=db.session,
            GuestPreview=GuestPreview,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user=second,
            token=preview.token,
        )
        assert lost is None
        db.session.refresh(preview)
        assert int(preview.claimed_user_id) == int(first.id)


def test_measured_pipeline_denies_org_viewer():
    from services.measured_pipeline import run_measured_only_pipeline

    with app.app_context():
        ensure_schema()
        suffix = uuid4().hex
        owner = User(
            email=f"meas-own-{suffix}@example.com",
            name="Owner",
            plan="business",
        )
        owner.set_password("MeasOwn!23456")
        viewer = User(
            email=f"meas-view-{suffix}@example.com",
            name="Viewer",
            plan="business",
        )
        viewer.set_password("MeasView!23456")
        db.session.add_all([owner, viewer])
        db.session.flush()
        org = ensure_personal_org(owner)
        db.session.add(
            OrganizationMember(
                organization_id=org.id, user_id=viewer.id, role="viewer"
            )
        )
        site = SiteAnalysis(
            user_id=owner.id,
            url=f"https://meas-{suffix}.example.com/",
            domain=f"meas-{suffix}.example.com",
            organization_id=org.id,
            aio_score=50,
            geo_score=50,
            findings_json="[]",
            crawl_pages_json="{}",
        )
        db.session.add(site)
        db.session.commit()
        try:
            run_measured_only_pipeline(
                db_session=db.session,
                SiteAnalysis=SiteAnalysis,
                AnalysisRun=AnalysisRun,
                user=viewer,
                url=site.url,
            )
            raised = False
        except PermissionError:
            raised = True
        assert raised is True


def test_job_status_findings_are_summaries_not_fix_bodies():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"job-find-{uuid4().hex}@example.com",
            name="Job",
            plan="business",
            role="internal",
        )
        user.set_password("JobFind!23456")
        raw, prefix, digest = generate_api_key()
        user.api_key_hash = digest
        user.api_key_prefix = prefix
        db.session.add(user)
        db.session.flush()
        site = SiteAnalysis(
            user_id=user.id,
            url="https://findings.example/",
            domain="findings.example",
            aio_score=10,
            geo_score=10,
            findings_json=json.dumps(
                [
                    {
                        "severity": "critical",
                        "title": "llms missing",
                        "category": "aio",
                        "detail": "SECRET_DETAIL",
                        "fix": "SECRET_FIX",
                    }
                ]
            ),
        )
        db.session.add(site)
        db.session.flush()
        job = AnalysisJob(
            user_id=user.id,
            url=site.url,
            status="done",
            site_id=site.id,
            billed_cents=0,
            held_cents=0,
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id

    client = app.test_client()
    resp = client.get(f"/api/v1/jobs/{job_id}", headers={"X-Api-Key": raw})
    assert resp.status_code == 200
    body = resp.get_json()
    findings = body.get("findings") or []
    assert findings
    blob = json.dumps(findings)
    assert "SECRET_DETAIL" not in blob
    assert "SECRET_FIX" not in blob
    assert findings[0]["title"] == "llms missing"


def test_plus_edge_routes_send_no_store():
    suffix = uuid4().hex
    token = f"plus-{suffix}"
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"edge-plus-{suffix}@example.com",
            name="Edge Plus",
            plan="plus",
        )
        user.set_password("EdgePlus!23456")
        db.session.add(user)
        db.session.flush()
        site = SiteAnalysis(
            user_id=user.id,
            url=f"https://edgep-{suffix}.example.com/",
            domain=f"edgep-{suffix}.example.com",
            public_token=token,
            signals_hosted=True,
            llms_txt="# plus",
            json_ld_artifact='{"@type":"Organization"}',
        )
        db.session.add(site)
        db.session.commit()

    client = app.test_client()
    robots = client.get(f"/e/{token}/robots.txt")
    assert robots.status_code == 200
    assert "no-store" in (robots.headers.get("Cache-Control") or "")
    llms = client.get(f"/e/{token}/llms.txt")
    assert llms.status_code == 200
    assert "max-age=60" in (llms.headers.get("Cache-Control") or "")
