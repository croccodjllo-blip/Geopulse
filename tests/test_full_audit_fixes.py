"""Full-audit regression tests for P1 fail-closed and tenancy/hold fixes."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import services.paddle_billing as pb
from app import AnalysisRun, SiteAnalysis, User, app, db, ensure_schema
from services.analysis_store import persist_analysis
from services.citation_monitor import sov_prompt_limit


def test_subscription_paid_plan_fail_closed(monkeypatch):
    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_plus")
    monkeypatch.setenv("PADDLE_PRICE_BUSINESS_MONTHLY", "pri_biz")
    # Unknown price ids → None (never invent plus).
    assert pb.subscription_paid_plan({"items": []}, current_plan="free") is None
    assert (
        pb.subscription_paid_plan({"items": []}, current_plan="plus") == "plus"
    )
    assert (
        pb.subscription_paid_plan(
            {"items": [{"price": {"id": "pri_biz"}}]}, current_plan="free"
        )
        == "business"
    )


def test_sov_prompt_limit_fast_mode(monkeypatch):
    monkeypatch.setenv("SOV_PROMPT_MODE", "fast")
    monkeypatch.setenv("SOV_FAST_PROMPTS", "3")
    monkeypatch.setenv("ANALYSIS_SOV_PROMPTS", "8")
    assert sov_prompt_limit() == 3
    monkeypatch.setenv("SOV_PROMPT_MODE", "full")
    assert sov_prompt_limit() == 8


def test_org_member_remesure_does_not_fork(monkeypatch):
    from centropic.tenancy import Organization, OrganizationMember, ensure_personal_org
    from services.analyze_pipeline import run_analysis_pipeline

    with app.app_context():
        ensure_schema()
        owner = User(
            email=f"own-{uuid4().hex}@example.com",
            name="Owner",
            plan="business",
        )
        owner.set_password("OwnTest!23456")
        member = User(
            email=f"mem-{uuid4().hex}@example.com",
            name="Member",
            plan="business",
        )
        member.set_password("MemTest!23456")
        db.session.add_all([owner, member])
        db.session.commit()
        org = ensure_personal_org(owner)
        db.session.add(
            OrganizationMember(
                organization_id=org.id, user_id=member.id, role="member"
            )
        )
        site = SiteAnalysis(
            user_id=owner.id,
            organization_id=org.id,
            url="https://shared.example.com/",
            domain="shared.example.com",
        )
        db.session.add(site)
        db.session.commit()
        site_id = site.id

        def _fake_analyze(*a, **k):
            return {
                "scraped": {"domain": "shared.example.com", "title": "Shared"},
                "aio_score": 50,
                "geo_score": 50,
                "findings": [],
                "pages": [],
                "probes": {},
                "signals": {},
            }

        monkeypatch.setattr(
            "services.analyze_pipeline.analyze_site", _fake_analyze
        )
        monkeypatch.setattr(
            "services.analyze_pipeline.run_geo_suite", lambda **k: None
        )
        monkeypatch.setattr(
            "services.analyze_pipeline.build_optimization_pack",
            lambda *a, **k: {},
        )

        out = run_analysis_pipeline(
            db_session=db.session,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user=member,
            url="https://shared.example.com/",
            openai_api_key=None,
            openai_model="gpt-4o-mini",
            source="manual",
        )
        assert out.id == site_id
        assert SiteAnalysis.query.filter_by(url="https://shared.example.com/").count() == 1
        assert out.user_id == owner.id
