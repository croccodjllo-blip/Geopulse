"""Plus/top-up checkout must require immediate-delivery waiver (fail-closed)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from services.legal_docs import DIGITAL_WAIVER_VERSION


def test_templates_and_js_wire_waiver_gate():
    pricing = Path("templates/pricing.html").read_text(encoding="utf-8")
    assert "digital_service_waiver" in pricing
    assert "accept_immediate_service" in pricing
    assert "data-checkout-gate" in pricing
    assert 'data-paddle-checkout="plus"' in pricing
    topup = Path("templates/topup.html").read_text(encoding="utf-8")
    assert "digital_service_waiver" in topup
    assert "data-checkout-gate" in topup
    partial = Path("templates/partials/digital_service_waiver.html").read_text(
        encoding="utf-8"
    )
    assert "data-digital-waiver-input" in partial
    assert "accept_immediate_service" in partial
    js = Path("static/js/paddle-checkout.js").read_text(encoding="utf-8")
    assert "requireWaiver" in js
    assert "recordWaiver" in js
    assert "accept_immediate_service" in js


def _verified_user(**kwargs):
    from app import User, db

    user = User(
        email=kwargs.pop("email", f"waiver-{uuid4().hex}@example.com"),
        name="Waiver",
        plan=kwargs.pop("plan", "free"),
        **kwargs,
    )
    user.set_password("WaiverTest!23456")
    user.email_verified_at = datetime.now(timezone.utc)
    db.session.add(user)
    db.session.commit()
    return user


def test_billing_checkout_requires_waiver_flag(monkeypatch):
    import services.paddle_billing as pb
    from app import app, db, ensure_schema

    monkeypatch.setattr(pb, "PADDLE_API_KEY", "test_key")
    monkeypatch.setattr(pb, "PADDLE_CLIENT_TOKEN", "test_token")
    monkeypatch.setattr(pb, "PADDLE_PRICE_PLUS", "pri_plus_test")
    monkeypatch.setattr(pb, "paddle_enabled", lambda: True)
    monkeypatch.setattr(pb, "paddle_overlay_ready", lambda: True)
    monkeypatch.setattr(pb, "paddle_plus_enabled", lambda: True)
    monkeypatch.setattr("app.payments_enabled", lambda: True)
    monkeypatch.setattr("app.payments_provider", lambda: "paddle")
    monkeypatch.setattr("app.paddle_overlay_ready", lambda: True)
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        ensure_schema()
        user = _verified_user()
        uid = user.id
        sv = int(user.session_version or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["session_version"] = sv

    blocked = client.post(
        "/billing/checkout",
        data={"product": "plus", "overlay": "1"},
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    assert blocked.status_code == 400
    body = blocked.get_json()
    assert body["error"] == "digital_service_waiver_required"

    ok = client.post(
        "/billing/checkout",
        data={
            "product": "plus",
            "overlay": "1",
            "accept_immediate_service": "y",
        },
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    assert ok.status_code == 200
    assert ok.get_json().get("ok") is True

    with app.app_context():
        from app import User

        u = db.session.get(User, uid)
        assert u.digital_service_waiver_at is not None
        assert u.digital_service_waiver_version == DIGITAL_WAIVER_VERSION


def test_logged_in_pricing_renders_waiver_checkbox(monkeypatch):
    import services.paddle_billing as pb
    from app import app, db, ensure_schema

    monkeypatch.setattr(pb, "paddle_enabled", lambda: True)
    monkeypatch.setattr(pb, "paddle_overlay_ready", lambda: True)
    monkeypatch.setattr(pb, "paddle_plus_enabled", lambda: True)
    monkeypatch.setattr("app.paddle_plus_enabled", lambda: True)
    monkeypatch.setattr("app.paddle_overlay_ready", lambda: True)
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        ensure_schema()
        user = _verified_user()
        uid = user.id
        sv = int(user.session_version or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["session_version"] = sv

    r = client.get("/prezzi")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "data-checkout-gate" in html
    assert "data-digital-waiver-input" in html
    assert "accept_immediate_service" in html
    assert 'data-paddle-checkout="plus"' in html or "billing_checkout" in html
