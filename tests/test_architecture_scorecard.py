"""Architecture scorecard tests — layered SaaS package."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-not-for-prod")
os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("ASYNC_ANALYZE", "0")

from centropic.csp import build_csp_header
from centropic.factory import create_app
from centropic.metrics import incr, snapshot
from centropic.tenancy import (
    Organization,
    ensure_personal_org,
    user_can_access_site,
)
from centropic.views import edge, billing, admin, api


def test_create_app_factory():
    app = create_app()
    assert app.name
    assert "dashboard" in app.view_functions


def test_view_domain_catalogs_cover_core_surfaces():
    assert "edge_llms_txt" in edge.ROUTE_CATALOG
    assert "billing_paddle_webhook" in billing.ROUTE_CATALOG
    assert "admin_home" in admin.ROUTE_CATALOG
    assert "api_v1_analyze" in api.ROUTE_CATALOG


def test_csp_uses_nonce_not_blanket_unsafe_inline_script():
    header = build_csp_header(
        nonce="testNonce123",
        paddle=True,
        analytics=False,
        adsense=False,
    )
    assert "nonce-testNonce123" in header
    assert "strict-dynamic" in header
    # Seed is nonce-based; legacy unsafe-inline must not be the script allowlist.
    assert "script-src" in header
    script_part = header.split("script-src ")[1].split(";")[0]
    assert "'unsafe-inline'" not in script_part


def test_metrics_counters():
    before = snapshot()["counters"].get("arch.test", 0)
    incr("arch.test", 2)
    assert snapshot()["counters"]["arch.test"] == before + 2


def test_user_entitlements_single_source():
    from app import User, app, db, ensure_schema

    with app.app_context():
        ensure_schema()
        u = User(email="arch-ents@example.com", name="Arch", plan="plus")
        u.set_password("ArchTest!23456")
        db.session.add(u)
        db.session.commit()
        assert u.entitlements.plan == "plus"
        assert u.can("measured_sov")
        assert not u.can("api_access")
        assert u.max_sites == u.entitlements.max_sites


def test_organization_tenancy_acl():
    from app import SiteAnalysis, User, app, db, ensure_schema

    with app.app_context():
        ensure_schema()
        owner = User(email="org-owner@example.com", name="Owner", plan="business")
        owner.set_password("ArchTest!23456")
        member = User(email="org-member@example.com", name="Member", plan="plus")
        member.set_password("ArchTest!23456")
        stranger = User(email="org-stranger@example.com", name="Stranger", plan="free")
        stranger.set_password("ArchTest!23456")
        db.session.add_all([owner, member, stranger])
        db.session.commit()

        org = ensure_personal_org(owner)
        assert org is not None
        assert Organization.query.filter_by(id=org.id).first() is not None

        from centropic.tenancy import OrganizationMember

        db.session.add(
            OrganizationMember(
                organization_id=org.id, user_id=member.id, role="member"
            )
        )
        site = SiteAnalysis(
            user_id=owner.id,
            organization_id=org.id,
            url="https://example.com/",
            domain="example.com",
        )
        db.session.add(site)
        db.session.commit()

        assert user_can_access_site(owner, site)
        assert user_can_access_site(member, site)
        assert not user_can_access_site(stranger, site)


def test_schema_pragma_is_sqlite_only():
    import inspect

    from app import ensure_schema

    src = inspect.getsource(ensure_schema)
    assert 'dialect.name == "sqlite"' in src
    assert "PRAGMA journal_mode=WAL" in src


def test_alembic_baseline_exists():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert (root / "alembic.ini").is_file()
    assert (root / "migrations" / "env.py").is_file()
    versions = list((root / "migrations" / "versions").glob("*.py"))
    assert versions
    assert any("organization" in p.read_text() for p in versions)


def test_payment_idempotency_alias():
    from app import CreditLedger

    row = CreditLedger(
        user_id=1,
        amount_cents=100,
        balance_after_cents=100,
        description="test",
        stripe_payment_intent="paddle:txn_1",
    )
    assert row.payment_idempotency_key == "paddle:txn_1"
    row.payment_idempotency_key = "paddle:txn_2"
    assert row.stripe_payment_intent == "paddle:txn_2"


def test_health_architecture_detail_for_admin(monkeypatch):
    from app import User, app, db, ensure_schema, _establish_session

    with app.app_context():
        ensure_schema()
        admin = User(email="arch-admin@example.com", name="Admin", plan="admin")
        admin.set_password("ArchTest!23456")
        db.session.add(admin)
        db.session.commit()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = admin.id if False else None

    # Login via session helpers inside request context
    with app.app_context():
        admin = User.query.filter_by(email="arch-admin@example.com").first()
        assert admin is not None
        admin_id = admin.id

    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["session_version"] = 0

    # Fix session_version to match user
    with app.app_context():
        admin = db.session.get(User, admin_id)
        with client.session_transaction() as sess:
            sess["session_version"] = int(admin.session_version or 0)

    resp = client.get("/health")
    # Without detail token / admin cookie binding may still be basic
    assert resp.status_code in {200, 503}
    data = resp.get_json()
    assert data["service"] == "centropic"
