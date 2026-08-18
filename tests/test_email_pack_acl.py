"""ACL: org viewers cannot email analysis packs."""

from __future__ import annotations

from uuid import uuid4

from app import SiteAnalysis, User, app, db, ensure_schema
from centropic.tenancy import Organization, OrganizationMember, ensure_personal_org


def test_email_pack_denied_for_org_viewer(monkeypatch):
    suffix = uuid4().hex
    prev_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        ensure_schema()
        owner = User(
            email=f"owner-pack-{suffix}@example.com",
            name="Owner",
            plan="business",
            credit_balance_cents=50_000,
        )
        owner.set_password("PackAcl!23456")
        viewer = User(
            email=f"viewer-pack-{suffix}@example.com",
            name="Viewer",
            plan="business",
            credit_balance_cents=50_000,
        )
        viewer.set_password("PackAcl!23456")
        db.session.add_all([owner, viewer])
        db.session.flush()
        org = ensure_personal_org(owner)
        db.session.add(
            OrganizationMember(
                organization_id=org.id, user_id=viewer.id, role="viewer"
            )
        )
        site = SiteAnalysis(
            user_id=owner.id,
            url=f"https://pack-{suffix}.example.com/",
            domain=f"pack-{suffix}.example.com",
            organization_id=org.id,
            aio_score=50,
            geo_score=50,
        )
        db.session.add(site)
        db.session.commit()
        site_id = int(site.id)
        viewer_id = int(viewer.id)
        session_ver = int(getattr(viewer, "session_version", 0) or 0)

    sent: list[dict] = []

    def _fake_send(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr("app.mail_configured", lambda: True)
    monkeypatch.setattr("app.send_email_with_attachment", _fake_send)

    client = app.test_client()
    try:
        with client.session_transaction() as sess:
            sess["user_id"] = viewer_id
            sess["session_version"] = session_ver

        resp = client.post(
            f"/dashboard/email-pack/{site_id}",
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        assert not sent
    finally:
        app.config["WTF_CSRF_ENABLED"] = prev_csrf


def test_dashboard_scripts_carry_csp_nonce():
    from pathlib import Path

    html = Path("templates/dashboard.html").read_text(encoding="utf-8")
    # Every script tag that loads JS must carry the CSP nonce.
    for line in html.splitlines():
        stripped = line.strip()
        if not stripped.startswith("<script"):
            continue
        if 'type="application/ld+json"' in stripped:
            continue
        assert 'nonce="{{ csp_nonce }}"' in stripped, stripped
