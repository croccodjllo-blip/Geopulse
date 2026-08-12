"""Registration phone prefix composition."""

from __future__ import annotations

import pytest

from app import RegisterForm, User, app, ensure_schema
from services.phone_prefixes import compose_phone, normalize_phone_prefix


@pytest.fixture
def client(monkeypatch):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    monkeypatch.setattr("app.limiter.allow", lambda *a, **k: True)
    with app.test_client() as c:
        with app.app_context():
            ensure_schema()
        yield c


def test_compose_phone_italy_default_trunk_zero():
    assert compose_phone("+39", "333 1234567") == "+393331234567"
    assert compose_phone("+39", "0333 1234567") == "+393331234567"


def test_compose_phone_full_international_ignores_prefix():
    assert compose_phone("+39", "+44 7700 900123") == "+447700900123"


def test_compose_phone_empty():
    assert compose_phone("+39", "") is None
    assert compose_phone("+39", "   ") is None


def test_normalize_phone_prefix_fallback():
    assert normalize_phone_prefix("") == "+39"
    assert normalize_phone_prefix("+999") == "+39"
    assert normalize_phone_prefix("33") == "+33"


def test_register_form_composes_phone_with_prefix():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_request_context(
        "/register",
        method="POST",
        data={
            "name": "Ada Lovelace",
            "email": "ada-phone@example.com",
            "password": "SecurePass1!",
            "confirm": "SecurePass1!",
            "accept_terms": "y",
            "phone_prefix": "+33",
            "phone": "6 12 34 56 78",
        },
    ):
        form = RegisterForm()
        assert form.validate(), form.errors
        assert form.phone.data == "+33612345678"


def test_register_stores_composed_phone(client, monkeypatch):
    monkeypatch.setattr("app.mail_configured", lambda: False)
    email = "phone-prefix@example.com"
    resp = client.post(
        "/register",
        data={
            "name": "Phone User",
            "email": email,
            "password": "SecurePass1!",
            "confirm": "SecurePass1!",
            "accept_terms": "y",
            "phone_prefix": "+49",
            "phone": "151 2345678",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        assert u is not None
        assert u.phone == "+491512345678"
