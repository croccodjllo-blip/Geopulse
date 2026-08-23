"""Pack deliverable: no code sheet; email via popup with custom address."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def test_pack_section_has_no_code_sheet():
    prompt = Path("templates/dashboard_prompt.html").read_text(encoding="utf-8")
    ops = Path("templates/partials/dash_prompt_ops.html").read_text(encoding="utf-8")
    assert "pack-fix-box" not in prompt and "pack-fix-box" not in ops
    assert "pack_fix_html" not in prompt and "pack_fix_html" not in ops
    assert "data-pack-mail-open" in ops
    assert 'name="to_email"' in ops
    assert "pack-mail.js" in prompt
    assert "pack-deliverable" in ops


def test_pack_mail_assets_exist():
    js = Path("static/js/pack-mail.js").read_text(encoding="utf-8")
    assert "showModal" in js
    assert "data-pack-mail-open" in js
    css = Path("static/css/app.css").read_text(encoding="utf-8")
    assert ".pack-deliverable" in css
    assert ".pack-mail__panel" in css


def _verified_user(**kwargs):
    from app import User

    user = User(**kwargs)
    user.set_password("PackTest!23456")
    user.email_verified_at = datetime.now(timezone.utc)
    return user


def test_email_pack_sends_to_requested_address(monkeypatch):
    from app import app, SiteAnalysis, db

    sent: dict[str, str] = {}

    def _fake_send(**kwargs):
        sent["to"] = kwargs.get("to_email") or ""
        sent["filename"] = kwargs.get("attachment_filename") or ""

    monkeypatch.setattr("app.mail_configured", lambda: True)
    monkeypatch.setattr("app.send_email_with_attachment", _fake_send)
    monkeypatch.setattr(
        "app.pack_fix_html_bytes", lambda analysis: b"<html>pack</html>"
    )
    monkeypatch.setattr("app.limiter.allow", lambda *a, **k: True)
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        user = _verified_user(
            email="owner-pack@example.com",
            name="Owner",
            plan="plus",
            credit_balance_cents=5000,
        )
        db.session.add(user)
        db.session.flush()
        site = SiteAnalysis(
            user_id=user.id,
            url="https://brand.example/",
            domain="brand.example",
            aio_score=50,
            geo_score=55,
            findings_json="[]",
            llms_txt="# brand",
        )
        db.session.add(site)
        db.session.commit()
        site_id = site.id
        user_id = user.id
        sv = int(getattr(user, "session_version", 0) or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["session_version"] = sv

    res = client.post(
        f"/dashboard/email-pack/{site_id}",
        data={"to_email": "colleague@example.com"},
        follow_redirects=False,
    )
    assert res.status_code in (302, 303)
    assert sent.get("to") == "colleague@example.com"


def test_email_pack_rejects_bad_address(monkeypatch):
    from app import app, SiteAnalysis, db

    monkeypatch.setattr("app.mail_configured", lambda: True)
    monkeypatch.setattr("app.limiter.allow", lambda *a, **k: True)
    app.config["WTF_CSRF_ENABLED"] = False
    called = {"n": 0}

    def _boom(**kwargs):
        called["n"] += 1

    monkeypatch.setattr("app.send_email_with_attachment", _boom)

    with app.app_context():
        user = _verified_user(
            email="owner-pack2@example.com",
            name="Owner",
            plan="plus",
            credit_balance_cents=5000,
        )
        db.session.add(user)
        db.session.flush()
        site = SiteAnalysis(
            user_id=user.id,
            url="https://brand2.example/",
            domain="brand2.example",
            aio_score=40,
            geo_score=42,
            findings_json="[]",
        )
        db.session.add(site)
        db.session.commit()
        site_id = site.id
        user_id = user.id
        sv = int(getattr(user, "session_version", 0) or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["session_version"] = sv

    res = client.post(
        f"/dashboard/email-pack/{site_id}",
        data={"to_email": "not-an-email"},
        follow_redirects=False,
    )
    assert res.status_code in (302, 303)
    assert called["n"] == 0
