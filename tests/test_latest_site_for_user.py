"""Dashboard latest site must follow updated_at (last analyzed), not created_at."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import SiteAnalysis, User, app, db, ensure_schema
from centropic.tenancy import latest_site_for_user


def test_latest_site_prefers_recently_updated_over_newer_created():
    with app.app_context():
        ensure_schema()
        now = datetime.now(timezone.utc)
        user = User(email="cvi-latest@example.com", name="L", plan="plus")
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()

        older = SiteAnalysis(
            user_id=user.id,
            url="https://centropic.ai/",
            domain="centropic.ai",
            aio_score=96,
            geo_score=100,
            created_at=now - timedelta(hours=2),
            updated_at=now,  # just re-analyzed
        )
        newer_created = SiteAnalysis(
            user_id=user.id,
            url="https://google.it/",
            domain="www.google.com",
            aio_score=41,
            geo_score=59,
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),  # preview claim, never re-run
        )
        db.session.add_all([older, newer_created])
        db.session.commit()

        latest = latest_site_for_user(SiteAnalysis, user)
        assert latest is not None
        assert latest.id == older.id
        assert latest.domain == "centropic.ai"


def test_latest_site_honors_prefer_site_id():
    with app.app_context():
        ensure_schema()
        now = datetime.now(timezone.utc)
        user = User(email="cvi-prefer@example.com", name="P", plan="plus")
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        a = SiteAnalysis(
            user_id=user.id,
            url="https://a.example/",
            domain="a.example",
            created_at=now,
            updated_at=now,
        )
        b = SiteAnalysis(
            user_id=user.id,
            url="https://b.example/",
            domain="b.example",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
        db.session.add_all([a, b])
        db.session.commit()

        picked = latest_site_for_user(SiteAnalysis, user, prefer_site_id=b.id)
        assert picked is not None
        assert picked.id == b.id
