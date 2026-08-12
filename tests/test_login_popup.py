"""Login page renders as a dismissible popup shell."""

from __future__ import annotations

import pytest

from app import app


@pytest.fixture
def client(monkeypatch):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    monkeypatch.setattr("app.limiter.allow", lambda *a, **k: True)
    with app.test_client() as c:
        yield c


def test_login_page_is_popup_shell(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "login-popup" in html
    assert 'role="dialog"' in html
    assert "login-popup__scrim" in html
    assert "login-popup__close" in html
    assert "auth-aside" not in html
    assert "body-login-popup" in html


def test_login_popup_preserves_next_on_form(client):
    resp = client.get("/login?next=/pricing")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'action="/login?next=/pricing"' in html or "next=/pricing" in html
