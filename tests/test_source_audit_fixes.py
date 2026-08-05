"""Source-audit P0/P1 regression tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from uuid import uuid4

from app import (
    CREDIT_LEDGER_PI_INDEX_OK,
    AnalysisJob,
    SiteAnalysis,
    User,
    app,
    db,
    ensure_schema,
    resolve_analyze_existing,
)
from centropic.tenancy import (
    Organization,
    OrganizationMember,
    ensure_personal_org,
    user_can_write_site,
)
from services.agency import build_whitelabel_html, normalize_primary_color


def test_normalize_primary_color_blocks_css_injection():
    assert normalize_primary_color("#6EC6C0") == "#6EC6C0"
    assert normalize_primary_color("red;}body{background:url(//x)}") == "#0B3D2E"
    html = build_whitelabel_html(
        site=type("S", (), {"domain": "ex.com", "url": "https://ex.com", "aio_score": 1, "geo_score": 2, "findings": []})(),
        agency={"primary_color": "red;}body{x:1}", "brand_name": "A"},
    )
    assert "red;}" not in html
    assert "#0B3D2E" in html


def test_org_viewer_cannot_remesure_shared_site():
    suffix = uuid4().hex
    with app.app_context():
        ensure_schema()
        owner = User(
            email=f"owner-acl-{suffix}@example.com",
            name="Owner",
            plan="business",
            credit_balance_cents=50_000,
        )
        owner.set_password("AclTest!23456")
        viewer = User(
            email=f"viewer-acl-{suffix}@example.com",
            name="Viewer",
            plan="business",
            credit_balance_cents=50_000,
        )
        viewer.set_password("AclTest!23456")
        db.session.add_all([owner, viewer])
        db.session.flush()
        org = ensure_personal_org(owner)
        assert org is not None
        db.session.add(
            OrganizationMember(
                organization_id=org.id, user_id=viewer.id, role="viewer"
            )
        )
        site = SiteAnalysis(
            user_id=owner.id,
            url=f"https://shared-{suffix}.example.com/",
            domain=f"shared-{suffix}.example.com",
            organization_id=org.id,
        )
        db.session.add(site)
        db.session.commit()

        assert user_can_write_site(owner, site) is True
        assert user_can_write_site(viewer, site) is False
        with app.test_request_context("/dashboard/analyze", method="POST"):
            existing, block = resolve_analyze_existing(
                viewer, f"https://shared-{suffix}.example.com/"
            )
            assert existing is not None
            assert block is not None
            # Member can remesure.
            member = User(
                email=f"member-acl-{suffix}@example.com",
                name="Member",
                plan="business",
                credit_balance_cents=50_000,
            )
            member.set_password("AclTest!23456")
            db.session.add(member)
            db.session.flush()
            db.session.add(
                OrganizationMember(
                    organization_id=org.id, user_id=member.id, role="member"
                )
            )
            db.session.commit()
            existing2, block2 = resolve_analyze_existing(
                member, f"https://shared-{suffix}.example.com/"
            )
            assert existing2 is not None
            assert block2 is None


def test_paddle_topup_no_user_returns_500(monkeypatch):
    secret = "pdl_ntfsec_audit"
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("PADDLE_TOPUP_PRICE_10", "pri_top10")
    # Force catalog recognition of amount if needed via monkeypatch of helpers.
    from services import paddle_billing as pb

    body_obj = {
        "event_type": "transaction.completed",
        "data": {
            "id": f"txn_nouser_{uuid4().hex[:8]}",
            "customer_id": "ctm_missing",
            "custom_data": {},
            "details": {"totals": {"grand_total": "1000", "currency_code": "EUR"}},
            "items": [{"price": {"id": "pri_top10"}, "quantity": 1}],
        },
    }
    body = json.dumps(body_obj).encode("utf-8")
    ts = str(int(time.time()))
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    header = f"ts={ts};h1={h1}"

    monkeypatch.setattr(pb, "topup_cents_for_transaction", lambda data: 1000)
    monkeypatch.setattr(
        "app.topup_cents_for_transaction", lambda data: 1000
    )
    monkeypatch.setattr("app._topup_credit_cents", lambda payment: 1000)
    monkeypatch.setattr(app, "CREDIT_LEDGER_PI_INDEX_OK", True, raising=False)
    # Module-level flag used inside webhook
    import app as app_mod

    app_mod.CREDIT_LEDGER_PI_INDEX_OK = True

    with app.app_context():
        ensure_schema()
        client = app.test_client()
        resp = client.post(
            "/billing/paddle-webhook",
            data=body,
            headers={"Paddle-Signature": header, "Content-Type": "application/json"},
        )
        assert resp.status_code == 500
        assert resp.get_json().get("error") == "no_user"


def test_credit_ledger_index_flag_blocks_topup(monkeypatch):
    import app as app_mod

    secret = "pdl_ntfsec_audit2"
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", secret)
    body_obj = {
        "event_type": "transaction.completed",
        "data": {
            "id": f"txn_idx_{uuid4().hex[:8]}",
            "customer_id": "ctm_x",
            "custom_data": {"centropic_user_id": "1"},
            "items": [{"price": {"id": "pri_top10"}, "quantity": 1}],
        },
    }
    body = json.dumps(body_obj).encode("utf-8")
    ts = str(int(time.time()))
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    header = f"ts={ts};h1={h1}"
    monkeypatch.setattr("app.topup_cents_for_transaction", lambda data: 1000)
    monkeypatch.setattr("app._topup_credit_cents", lambda payment: 1000)

    with app.app_context():
        ensure_schema()
        app_mod.CREDIT_LEDGER_PI_INDEX_OK = False
        try:
            client = app.test_client()
            resp = client.post(
                "/billing/paddle-webhook",
                data=body,
                headers={
                    "Paddle-Signature": header,
                    "Content-Type": "application/json",
                },
            )
            assert resp.status_code == 503
            assert resp.get_json().get("error") == "ledger_index_missing"
        finally:
            app_mod.CREDIT_LEDGER_PI_INDEX_OK = True
