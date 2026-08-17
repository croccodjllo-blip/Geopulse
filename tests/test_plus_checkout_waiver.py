"""Plus/top-up checkout: waiver modal + fail-closed consent before Paddle."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from services.legal_docs import DIGITAL_WAIVER_VERSION


def test_templates_and_js_wire_waiver_popup():
    pricing = Path("templates/pricing.html").read_text(encoding="utf-8")
    assert 'data-paddle-checkout="plus"' in pricing
    assert "Paga Plus" in pricing
    plus_block = pricing[pricing.index('id="plus"') : pricing.index('id="business"')]
    # Overlay path: button only; waiver lives in shared dialog (base), not always-on card.
    assert 'data-paddle-checkout="plus"' in plus_block
    assert "data-digital-waiver-dialog" not in plus_block

    base = Path("templates/base.html").read_text(encoding="utf-8")
    assert "digital_service_waiver_dialog.html" in base

    dialog = Path("templates/partials/digital_service_waiver_dialog.html").read_text(
        encoding="utf-8"
    )
    assert "data-digital-waiver-dialog" in dialog
    assert "data-digital-waiver-input" in dialog
    assert "Conferma obbligatoria prima del pagamento" in dialog
    assert "Continua al pagamento" in dialog

    js = Path("static/js/paddle-checkout.js").read_text(encoding="utf-8")
    assert "openWaiverDialog" in js
    assert "/billing/accept-immediate-service" in js
    assert "Checkout.open" in js
    assert "recordWaiver" in js


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


def test_accept_immediate_service_endpoint(monkeypatch):
    from app import app, db, ensure_schema

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
        "/billing/accept-immediate-service",
        data={},
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    assert blocked.status_code == 400
    assert blocked.get_json()["error"] == "digital_service_waiver_required"

    ok = client.post(
        "/billing/accept-immediate-service",
        data={"accept_immediate_service": "y"},
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    assert ok.status_code == 200
    body = ok.get_json()
    assert body["ok"] is True
    assert body["waiver_version"] == DIGITAL_WAIVER_VERSION

    with app.app_context():
        from app import User

        refreshed = db.session.get(User, uid)
        assert refreshed.digital_service_waiver_at is not None
        assert refreshed.digital_service_waiver_version == DIGITAL_WAIVER_VERSION


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

    allowed = client.post(
        "/billing/checkout",
        data={
            "product": "plus",
            "overlay": "1",
            "accept_immediate_service": "y",
        },
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    assert allowed.status_code == 200
    assert allowed.get_json()["ok"] is True
    assert allowed.get_json()["mode"] == "overlay"

    with app.app_context():
        from app import User

        refreshed = db.session.get(User, uid)
        assert refreshed.digital_service_waiver_at is not None
        assert refreshed.digital_service_waiver_version == DIGITAL_WAIVER_VERSION


def test_logged_in_prezzi_has_checkout_button_and_dialog(monkeypatch):
    import services.paddle_billing as pb
    from app import app, ensure_schema

    monkeypatch.setattr(pb, "PADDLE_CLIENT_TOKEN", "test_token")
    monkeypatch.setattr(pb, "PADDLE_PRICE_PLUS", "pri_plus_test")
    monkeypatch.setattr(pb, "paddle_overlay_ready", lambda: True)
    monkeypatch.setattr(pb, "paddle_plus_enabled", lambda: True)
    monkeypatch.setattr("app.paddle_overlay_ready", lambda: True)
    monkeypatch.setattr("app.paddle_plus_enabled", lambda: True)
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

    page = client.get("/prezzi")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert 'data-paddle-checkout="plus"' in html
    assert "Paga Plus" in html
    assert "data-digital-waiver-dialog" in html
    assert "Conferma obbligatoria prima del pagamento" in html
    # Title must live in the dialog, not as always-visible card chrome.
    assert html.count("Conferma obbligatoria prima del pagamento") >= 1
