"""P0 security fixes: open redirect, session invalidation, admin top-up allowlist."""

from __future__ import annotations

from flask import request

from app import ADMIN_TOPUP_AMOUNTS_CENTS, User, app, db, ensure_schema
from services.security import safe_next_url, safe_same_origin_url


def test_safe_same_origin_blocks_host_prefix_trick(monkeypatch):
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://centropic.ai")
    with app.test_request_context("/", base_url="https://centropic.ai/"):
        assert safe_same_origin_url("https://centropic.ai/dashboard", request) == "/dashboard"
        assert safe_same_origin_url("https://centropic.ai.evil.com/phish", request) is None
        assert safe_same_origin_url("//evil.test/phish", request) is None
        assert safe_same_origin_url("https://evil.test/phish", request) is None
        assert safe_same_origin_url("/lang/en", request) == "/lang/en"
        assert safe_same_origin_url("/\\evil", request) is None


def test_lang_referer_open_redirect_blocked(monkeypatch):
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://centropic.ai")
    with app.test_client() as client:
        resp = client.get(
            "/lang/en",
            headers={"Referer": "https://centropic.ai.evil.com/steal"},
            base_url="https://centropic.ai/",
            follow_redirects=False,
        )
        assert resp.status_code in {302, 303}
        loc = resp.headers.get("Location", "")
        assert "evil.com" not in loc


def test_lang_referer_same_origin_allowed(monkeypatch):
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://centropic.ai")
    with app.test_client() as client:
        resp = client.get(
            "/lang/de",
            headers={"Referer": "https://centropic.ai/prezzi"},
            base_url="https://centropic.ai/",
            follow_redirects=False,
        )
        assert resp.status_code in {302, 303}
        assert resp.headers.get("Location", "").endswith("/prezzi")


def test_session_invalidated_after_password_change():
    with app.app_context():
        ensure_schema()
        u = User(email="sess-reset@example.com", name="S", plan="free")
        u.set_password("OldPass123!")
        db.session.add(u)
        db.session.commit()
        uid = u.id
        ver = int(u.session_version)

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = uid
            sess["session_version"] = ver

        dash = client.get("/dashboard", follow_redirects=False)
        # Authenticated users get 200 (or redirect within app, not to login)
        loc = dash.headers.get("Location") or ""
        assert "login" not in loc
        assert dash.status_code in {200, 302, 303}

        with app.app_context():
            user = db.session.get(User, uid)
            assert user is not None
            user.set_password("NewPass456!")
            db.session.commit()
            assert int(user.session_version) == ver + 1

        dash2 = client.get("/dashboard", follow_redirects=False)
        assert dash2.status_code in {302, 303}
        assert "login" in (dash2.headers.get("Location") or "")


def test_admin_topup_allowlist():
    assert ADMIN_TOPUP_AMOUNTS_CENTS == frozenset({1000, 5000, 10000})
    assert 999999 not in ADMIN_TOPUP_AMOUNTS_CENTS


def test_safe_next_url_still_blocks_open_redirects():
    assert safe_next_url("//evil.test") == "/"
    assert safe_next_url("https://evil.test/phish") == "/"
    assert safe_next_url("/dashboard?job=1") == "/dashboard?job=1"
    assert safe_next_url("/%2f%2fevil.test") == "/"
