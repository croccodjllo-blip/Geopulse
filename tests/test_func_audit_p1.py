"""Functionality-audit residuals: Paddle leftover, Ads/GA4 health, admin mismatch."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app import User, app, db, ensure_schema
from services.paddle_billing import (
    classify_plan_paddle_mismatches,
    clear_stale_subscription_binding,
    stamp_unstamped_plan_sources,
)


def test_clear_stale_subscription_binding_only_on_free():
    free = SimpleNamespace(
        is_admin=False, plan="free", paddle_subscription_id="sub_x"
    )
    assert clear_stale_subscription_binding(free) is True
    assert free.paddle_subscription_id is None

    plus = SimpleNamespace(
        is_admin=False, plan="plus", paddle_subscription_id="sub_y"
    )
    assert clear_stale_subscription_binding(plus) is False
    assert plus.paddle_subscription_id == "sub_y"

    admin = SimpleNamespace(
        is_admin=True, plan="free", paddle_subscription_id="sub_z"
    )
    assert clear_stale_subscription_binding(admin) is False
    assert admin.paddle_subscription_id == "sub_z"


def test_classify_plan_paddle_mismatches_splits_grant_and_leftover():
    grant = SimpleNamespace(
        is_admin=False,
        plan="business",
        paddle_subscription_id=None,
        plan_source="grant",
    )
    unlabeled = SimpleNamespace(
        is_admin=False,
        plan="plus",
        paddle_subscription_id=None,
        plan_source=None,
    )
    rows = classify_plan_paddle_mismatches(
        [
            grant,
            unlabeled,
            SimpleNamespace(
                is_admin=False,
                plan="plus",
                paddle_subscription_id="sub_paid",
                plan_source="paddle",
            ),
            SimpleNamespace(
                is_admin=False,
                plan="free",
                paddle_subscription_id="sub_old",
                plan_source=None,
            ),
            SimpleNamespace(
                is_admin=True,
                plan="admin",
                paddle_subscription_id=None,
                plan_source=None,
            ),
        ]
    )
    assert len(rows["complimentary_grants"]) == 1
    assert rows["complimentary_grants"][0] is grant
    assert len(rows["paid_without_subscription"]) == 1
    assert rows["paid_without_subscription"][0] is unlabeled
    assert len(rows["free_with_subscription"]) == 1
    assert rows["free_with_subscription"][0].paddle_subscription_id == "sub_old"


def test_stamp_unstamped_plan_sources_never_changes_plan():
    grant = SimpleNamespace(
        is_admin=False, plan="business", paddle_subscription_id=None, plan_source=None
    )
    paid = SimpleNamespace(
        is_admin=False,
        plan="plus",
        paddle_subscription_id="sub_keep",
        plan_source=None,
    )
    already = SimpleNamespace(
        is_admin=False,
        plan="business",
        paddle_subscription_id=None,
        plan_source="grant",
    )
    n = stamp_unstamped_plan_sources([grant, paid, already])
    assert n == 2
    assert grant.plan == "business"
    assert grant.plan_source == "grant"
    assert paid.plan == "plus"
    assert paid.paddle_subscription_id == "sub_keep"
    assert paid.plan_source == "paddle"
    assert already.plan_source == "grant"


def test_current_user_clears_free_leftover_subscription():
    suffix = uuid4().hex
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"leftover-{suffix}@example.com",
            name="Leftover",
            plan="free",
            email_verified_at=datetime.now(timezone.utc),
            paddle_subscription_id=f"sub_{suffix}",
            paddle_customer_id=f"ctm_{suffix}",
        )
        user.set_password("Leftover!23456")
        db.session.add(user)
        db.session.commit()
        uid, sv = user.id, int(user.session_version or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["session_version"] = sv
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    with app.app_context():
        again = db.session.get(User, uid)
        assert again is not None
        assert again.plan == "free"
        assert again.paddle_subscription_id is None
        assert again.paddle_customer_id == f"ctm_{suffix}"


def test_health_detail_reports_attribution_without_failing_public(monkeypatch):
    token = f"attr-{uuid4().hex}"
    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", token)
    monkeypatch.setenv("CENTROPIC_SKIP_PROD_GUARDS", "1")
    with app.app_context():
        ensure_schema()
    client = app.test_client()
    public = client.get("/health")
    assert public.status_code == 200
    body = public.get_json()
    assert body["ok"] is True
    assert "attribution" not in body

    detail = client.get("/health", headers={"X-Ops-Token": token}).get_json()
    assert "attribution" in detail
    attr = detail["attribution"]
    assert set(attr) >= {
        "ga4",
        "ga4_measurement_protocol",
        "google_ads",
        "google_ads_plus_label",
        "google_ads_topup_label",
        "google_ads_checkout_label",
    }
    assert attr["google_ads"] is False
    assert attr["ga4_measurement_protocol"] is False
    assert "analyze_activity" in detail
    assert "analyze_activity" not in body


def test_csrf_failure_emits_real_csp_nonce():
    prev = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        with app.app_context():
            ensure_schema()
        client = app.test_client()
        resp = client.post("/anteprima", data={"url": "https://example.com"})
        assert resp.status_code == 400
        csp = resp.headers.get("Content-Security-Policy") or ""
        assert "script-src" in csp
        assert "'nonce-'" not in csp
        assert "nonce-" in csp
    finally:
        app.config["WTF_CSRF_ENABLED"] = prev


def test_admin_lists_paddle_mismatches():
    suffix = uuid4().hex
    with app.app_context():
        ensure_schema()
        admin = User(
            email=f"adm-{suffix}@example.com",
            name="Adm",
            plan="admin",
            role="admin",
            email_verified_at=datetime.now(timezone.utc),
        )
        admin.set_password("Admin!23456")
        grant = User(
            email=f"grant-{suffix}@example.com",
            name="Grant",
            plan="business",
            plan_source="grant",
            email_verified_at=datetime.now(timezone.utc),
        )
        grant.set_password("Grant!23456")
        drift = User(
            email=f"drift-{suffix}@example.com",
            name="Drift",
            plan="plus",
            email_verified_at=datetime.now(timezone.utc),
        )
        drift.set_password("Drift!23456")
        leftover = User(
            email=f"free-sub-{suffix}@example.com",
            name="FreeSub",
            plan="free",
            email_verified_at=datetime.now(timezone.utc),
            paddle_subscription_id=f"sub_admin_{suffix}",
        )
        leftover.set_password("FreeSub!23456")
        db.session.add_all([admin, grant, drift, leftover])
        db.session.commit()
        aid, sv = admin.id, int(admin.session_version or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = aid
        sess["session_version"] = sv
    html = client.get("/admin").get_data(as_text=True)
    assert "Ultima analisi" in html
    assert "Error fixture" in html
    assert "Grant piano (tenuti)" in html
    assert f"grant-{suffix}@example.com" in html
    assert "Disallineamento piano / Paddle" in html
    assert f"drift-{suffix}@example.com" in html
    assert f"free-sub-{suffix}@example.com" in html
    assert "senza Paddle" in html
    assert "subscription leftover" in html


def test_admin_set_plan_stamps_grant_without_downgrade():
    suffix = uuid4().hex
    with app.app_context():
        ensure_schema()
        admin = User(
            email=f"adm-set-{suffix}@example.com",
            name="Adm",
            plan="admin",
            role="admin",
            email_verified_at=datetime.now(timezone.utc),
        )
        admin.set_password("Admin!23456")
        target = User(
            email=f"keep-{suffix}@example.com",
            name="Keep",
            plan="free",
            email_verified_at=datetime.now(timezone.utc),
        )
        target.set_password("Keep!23456")
        db.session.add_all([admin, target])
        db.session.commit()
        aid, tid = admin.id, target.id
        sv = int(admin.session_version or 0)

    prev_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = aid
            sess["session_version"] = sv
        resp = client.post(
            f"/admin/set-plan/{tid}/business",
            follow_redirects=True,
        )
        assert resp.status_code == 200
    finally:
        app.config["WTF_CSRF_ENABLED"] = prev_csrf
    with app.app_context():
        again = db.session.get(User, tid)
        assert again is not None
        assert again.plan == "business"
        assert again.plan_source == "grant"
        assert not (again.paddle_subscription_id or "").strip()
