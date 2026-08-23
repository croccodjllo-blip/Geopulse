"""Multi-site dashboard: sticky ?site=, switcher, geo-ui site pin."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import SiteAnalysis, SovSnapshot, User, app, db, ensure_schema
from services.geo_ui_payload import build_geo_ui_payload


def _login(client, user: User) -> None:
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["session_version"] = int(getattr(user, "session_version", 0) or 0)


def _plus_user_with_two_sites(*, email: str) -> tuple[User, SiteAnalysis, SiteAnalysis]:
    now = datetime.now(timezone.utc)
    user = User(
        email=email,
        name="Multi",
        plan="plus",
        email_verified_at=now,
    )
    user.set_password("x" * 12)
    db.session.add(user)
    db.session.commit()
    a = SiteAnalysis(
        user_id=user.id,
        url="https://alpha.example/",
        domain="alpha.example",
        aio_score=80,
        geo_score=70,
        page_title="Alpha",
        created_at=now - timedelta(hours=2),
        updated_at=now,
    )
    b = SiteAnalysis(
        user_id=user.id,
        url="https://beta.example/",
        domain="beta.example",
        aio_score=40,
        geo_score=50,
        page_title="Beta",
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )
    db.session.add_all([a, b])
    db.session.commit()
    return user, a, b


def test_dashboard_site_query_loads_full_report_for_that_site():
    with app.app_context():
        ensure_schema()
        user, a, b = _plus_user_with_two_sites(email="ms-query@example.com")
        client = app.test_client()
        _login(client, user)
        resp = client.get(f"/dashboard?site={b.id}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "beta.example" in html
        assert 'id="dash-site-select"' in html
        assert f'data-site-id="{b.id}"' in html
        assert "is-active" in html
        assert "<select" not in html.split('id="analyze-panel"')[1][:4000]
        # Full report chrome for the selected site
        assert "AIO" in html and "GEO" in html


def test_dashboard_sticky_site_survives_bare_navigation():
    with app.app_context():
        ensure_schema()
        user, a, b = _plus_user_with_two_sites(email="ms-sticky@example.com")
        client = app.test_client()
        _login(client, user)
        assert client.get(f"/dashboard?site={b.id}").status_code == 200
        with client.session_transaction() as sess:
            assert int(sess.get("dashboard_site_id")) == b.id
        resp = client.get("/dashboard")
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "beta.example" in html
        assert "alpha.example" in html  # still listed in switcher
        assert 'id="result-domain"' in html
        # Primary report H2 is the sticky site
        idx = html.find('id="result-domain"')
        assert idx > 0
        assert "beta.example" in html[idx : idx + 80]


def test_free_single_site_has_no_switcher():
    with app.app_context():
        ensure_schema()
        now = datetime.now(timezone.utc)
        user = User(
            email="ms-free@example.com",
            name="Free",
            plan="free",
            email_verified_at=now,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        site = SiteAnalysis(
            user_id=user.id,
            url="https://solo.example/",
            domain="solo.example",
            aio_score=55,
            geo_score=60,
            created_at=now,
            updated_at=now,
        )
        db.session.add(site)
        db.session.commit()
        client = app.test_client()
        _login(client, user)
        html = client.get("/dashboard").get_data(as_text=True)
        assert "solo.example" in html
        assert "dash-site-select" not in html


def test_geo_ui_payload_honors_prefer_site_id():
    with app.app_context():
        ensure_schema()
        user, a, b = _plus_user_with_two_sites(email="ms-geo@example.com")
        with app.test_request_context("/"):
            payload = build_geo_ui_payload(
                user=user,
                SiteAnalysis=SiteAnalysis,
                SovSnapshot=SovSnapshot,
                prefer_site_id=b.id,
            )
        assert payload.get("domain") == "beta.example"
        assert payload.get("aioScore") == 40


def test_geo_ui_route_pins_site_query():
    with app.app_context():
        ensure_schema()
        user, a, b = _plus_user_with_two_sites(email="ms-geo-route@example.com")
        client = app.test_client()
        _login(client, user)
        resp = client.get(f"/dashboard/geo-ui?site={b.id}")
        assert resp.status_code in {200, 404}  # 404 if geo assets missing in CI
        if resp.status_code == 200:
            html = resp.get_data(as_text=True)
            assert "beta.example" in html
            assert '"domain": "beta.example"' in html or "beta.example" in html
        with client.session_transaction() as sess:
            assert int(sess.get("dashboard_site_id")) == b.id


def test_capability_exports_can_multi_site():
    from app import capability_template_vars

    with app.app_context():
        ensure_schema()
        plus = User(email="ms-cap-plus@example.com", name="P", plan="plus")
        plus.set_password("x" * 12)
        free = User(email="ms-cap-free@example.com", name="F", plan="free")
        free.set_password("x" * 12)
        db.session.add_all([plus, free])
        db.session.commit()
        assert capability_template_vars(plus)["can_multi_site"] is True
        assert capability_template_vars(free)["can_multi_site"] is False
