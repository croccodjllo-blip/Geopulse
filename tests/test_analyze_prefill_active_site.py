"""Analyze form URL defaults to the active dashboard site (or empty)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import SiteAnalysis, User, app, db, ensure_schema


def _login(client, user: User) -> None:
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["session_version"] = int(getattr(user, "session_version", 0) or 0)


def test_analyze_url_prefills_active_site():
    with app.app_context():
        ensure_schema()
        now = datetime.now(timezone.utc)
        user = User(
            email="prefill-active@example.com",
            name="P",
            plan="plus",
            website_url="https://profile-should-not-win.example/",
            email_verified_at=now,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        a = SiteAnalysis(
            user_id=user.id,
            url="https://alpha.example/",
            domain="alpha.example",
            created_at=now,
            updated_at=now,
        )
        b = SiteAnalysis(
            user_id=user.id,
            url="https://beta.example/",
            domain="beta.example",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
        db.session.add_all([a, b])
        db.session.commit()

        client = app.test_client()
        _login(client, user)
        html = client.get(f"/dashboard?site={b.id}").get_data(as_text=True)
        assert 'id="url"' in html
        assert 'value="https://beta.example/"' in html
        assert "profile-should-not-win" not in html


def test_analyze_url_empty_when_no_sites():
    with app.app_context():
        ensure_schema()
        now = datetime.now(timezone.utc)
        user = User(
            email="prefill-empty@example.com",
            name="E",
            plan="free",
            website_url="https://only-on-profile.example/",
            email_verified_at=now,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        _login(client, user)
        html = client.get("/dashboard").get_data(as_text=True)
        assert 'id="url"' in html
        assert "only-on-profile" not in html
        # Empty value (or no value attr) on the analyze input
        assert 'value="https://only-on-profile.example/"' not in html
