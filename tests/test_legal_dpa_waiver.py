"""DPA Art. 28 download + digital-service waiver on paid checkout."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from services.legal_docs import (
    DIGITAL_WAIVER_VERSION,
    DPA_VERSION,
    active_sub_processors,
    render_dpa_plaintext,
    sub_processors,
)


def test_dpa_plaintext_has_art28_and_annex():
    body = render_dpa_plaintext(company_name="Engineering Factory")
    assert "Art. 28" in body or "ARTICLE 28" in body.upper() or "Art. 28" in body
    assert "ANNEX A" in body
    assert DPA_VERSION in body
    assert "Paddle" in body or any(sp.name.startswith("Paddle") for sp in sub_processors())


def test_templates_wire_dpa_and_waiver():
    dpa = Path("templates/dpa.html").read_text(encoding="utf-8")
    assert "dpa_download" in dpa
    assert "Allegato A" in dpa or "sub_processors" in dpa
    pricing = Path("templates/pricing.html").read_text(encoding="utf-8")
    assert 'data-paddle-checkout="plus"' in pricing or "digital_service_waiver" in pricing
    assert "accept_immediate_service" in Path(
        "templates/partials/digital_service_waiver_dialog.html"
    ).read_text(encoding="utf-8") or "accept_immediate_service" in pricing
    topup = Path("templates/topup.html").read_text(encoding="utf-8")
    assert "topup" in topup.lower()
    js = Path("static/js/paddle-checkout.js").read_text(encoding="utf-8")
    assert "recordWaiver" in js or "requireWaiver" in js
    assert "Checkout.open" in js or "openPlus" in js


def test_dpa_routes_public():
    from app import app

    client = app.test_client()
    r = client.get("/dpa")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "DPA" in html or "sub-responsabili" in html.lower() or "Art. 28" in html
    r2 = client.get("/sub-responsabili")
    assert r2.status_code == 200
    r3 = client.get("/dpa.txt")
    assert r3.status_code == 200
    assert "attachment" in (r3.headers.get("Content-Disposition") or "")
    assert "noindex" in (r3.headers.get("X-Robots-Tag") or "").lower()
    ctype = (r3.headers.get("Content-Type") or "").lower()
    assert ctype.count("charset=") <= 1
    assert b"ANNEX A" in r3.data
    # Legacy .md must not be an attachment crawl error — redirect to HTML DPA.
    r4 = client.get("/dpa.md", follow_redirects=False)
    assert r4.status_code in {301, 302}
    assert "/dpa" in (r4.headers.get("Location") or "")


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


def test_billing_checkout_requires_waiver(monkeypatch):
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

    # Missing waiver → blocked JSON
    blocked = client.post(
        "/billing/checkout",
        data={"product": "plus", "overlay": "1"},
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    assert blocked.status_code == 400
    assert blocked.get_json()["error"] == "digital_service_waiver_required"

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


def test_active_subprocessors_list_nonempty_with_hosting():
    # Hosting row is always active.
    rows = active_sub_processors()
    assert any("Hosting" in r.name or "VPS" in r.name for r in rows)
