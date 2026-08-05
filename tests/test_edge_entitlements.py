"""Edge full artifacts remain a paid-plan capability."""

from __future__ import annotations

from uuid import uuid4

from app import SiteAnalysis, User, app, db, ensure_schema


def test_free_edge_full_artifact_returns_402_and_basic_keeps_brand_headers():
    suffix = uuid4().hex
    token = f"free-{suffix}"
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"edge-free-{suffix}@example.com",
            name="Edge Free",
            plan="free",
        )
        user.set_password("EdgeTest!23456")
        db.session.add(user)
        db.session.flush()
        site = SiteAnalysis(
            user_id=user.id,
            url=f"https://edge-{suffix}.example.com/",
            domain=f"edge-{suffix}.example.com",
            public_token=token,
            signals_hosted=True,
            llms_txt="# Edge Free",
        )
        db.session.add(site)
        db.session.commit()

    client = app.test_client()
    blocked = client.get(f"/e/{token}/robots.txt")
    assert blocked.status_code == 402
    assert blocked.get_json()["error"] == "plus_required"

    basic = client.get(f"/e/{token}/llms.txt", headers={"User-Agent": "GPTBot"})
    assert basic.status_code == 200
    assert basic.headers["X-Centropic-Edge"] == "1"
    assert basic.headers["X-Centropic-Version"] == "1"
    assert basic.headers["X-Centropic-Bot"] == "1"
    assert basic.headers["X-GeoPulse-Edge"] == "1"
