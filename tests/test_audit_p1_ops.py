"""P1 ops: webhook-gated Ads, hreflang/noindex, no hashed email in HTML."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app import User, app, db, ensure_schema, queue_analytics_event
from services.seo import hreflang_enabled_for_request, is_private_html_path

ROOT = Path(__file__).resolve().parents[1]


def test_billing_success_does_not_queue_subscribe_on_get():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    success = src.split("def billing_success():", 1)[1].split("def ", 1)[0]
    assert "queue_analytics_event" not in success
    assert "ads_plus_conversion_pending" in src
    assert "_queue_plus_subscribe_conversion" in src


def test_queue_analytics_event_strips_user_data(monkeypatch):
    monkeypatch.setattr("app.GA4_MEASUREMENT_ID", "G-TEST")
    with app.test_request_context("/"):
        from flask import session

        session.clear()
        queue_analytics_event(
            "subscribe",
            {"value": 1, "user_data": {"sha256_email_address": "abc"}},
        )
        events = session.get("analytics_events") or []
        assert events
        assert "user_data" not in events[-1]["params"]
        assert events[-1]["params"]["value"] == 1


def test_hreflang_skips_dashboard_keeps_landing():
    assert hreflang_enabled_for_request("index", "/") is True
    assert hreflang_enabled_for_request("pricing", "/prezzi") is True
    assert hreflang_enabled_for_request("register", "/register") is True
    assert hreflang_enabled_for_request("dashboard", "/dashboard") is False
    assert hreflang_enabled_for_request("login", "/login") is False
    assert is_private_html_path("dashboard", "/dashboard") is True
    assert is_private_html_path("index", "/") is False


def test_landing_still_has_hreflang_cluster():
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'rel="alternate" hreflang="en"' in html


def test_login_and_dashboard_noindex_header():
    login = app.test_client().get("/login")
    assert "noindex" in (login.headers.get("X-Robots-Tag") or "").lower() or "noindex" in login.get_data(
        as_text=True
    ).lower()

    with app.app_context():
        ensure_schema()
        u = User(
            email=f"p1-{uuid4().hex}@example.com",
            name="P1",
            plan="plus",
            email_verified_at=datetime.now(timezone.utc),
        )
        u.set_password("P1OpsTest!23456")
        db.session.add(u)
        db.session.commit()
        uid, sv = u.id, int(u.session_version or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["session_version"] = sv
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    html = dash.get_data(as_text=True)
    assert 'rel="alternate" hreflang="en"' not in html
    assert "noindex" in (dash.headers.get("X-Robots-Tag") or "").lower()


def test_gclid_cookie_sets_secure_on_https():
    js = (ROOT / "static/js/analytics.js").read_text(encoding="utf-8")
    assert ";Secure" in js
    assert "location.protocol" in js


def test_flush_plus_pending_queues_subscribe_once(monkeypatch):
    monkeypatch.setattr("app.GA4_MEASUREMENT_ID", "G-TEST")
    from flask import session

    from app import flush_pending_ads_conversions

    with app.app_context():
        ensure_schema()
        u = User(
            email=f"p1c-{uuid4().hex}@example.com",
            name="P1c",
            plan="plus",
            email_verified_at=datetime.now(timezone.utc),
            ads_plus_conversion_pending=True,
        )
        u.set_password("P1OpsTest!23456")
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with app.test_request_context("/dashboard"):
        user = db.session.get(User, uid)
        flush_pending_ads_conversions(user)
        events = session.get("analytics_events") or []
        names = [e["name"] for e in events]
        assert "subscribe" in names
        assert all("user_data" not in (e.get("params") or {}) for e in events)

    with app.app_context():
        again = db.session.get(User, uid)
        assert again.ads_plus_conversion_pending is False
