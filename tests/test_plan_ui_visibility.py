"""UI shows only services available on the user's plan (no locked upsells)."""

from __future__ import annotations

from uuid import uuid4

from app import User, app, capability_template_vars, db, ensure_schema


def _user(plan: str) -> User:
    user = User(
        email=f"ui-{plan}-{uuid4().hex}@example.com",
        name=plan,
        plan=plan,
    )
    user.set_password("UiPlanTest!23456")
    db.session.add(user)
    db.session.commit()
    return user


def _client_for(user_id: int, session_version: int):
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["session_version"] = session_version
    return client


def test_capability_template_vars_per_plan():
    free = type(
        "U", (), {"is_pro": False, "is_business": False, "is_admin": False, "plan": "free"}
    )()
    plus = type(
        "U", (), {"is_pro": True, "is_business": False, "is_admin": False, "plan": "plus"}
    )()
    biz = type(
        "U", (), {"is_pro": True, "is_business": True, "is_admin": False, "plan": "business"}
    )()

    free_caps = capability_template_vars(free)
    plus_caps = capability_template_vars(plus)
    biz_caps = capability_template_vars(biz)

    assert free_caps["can_alerts"] is False
    assert free_caps["can_api"] is False
    assert free_caps["can_agency"] is False
    assert free_caps["can_measured_sov"] is False
    assert free_caps["dash_plan"] == "free"
    assert any(s["id"] == "sov_proxy" for s in free_caps["plan_services"])
    assert not any(s["id"] == "api_access" for s in free_caps["plan_services"])

    assert plus_caps["can_alerts"] is True
    assert plus_caps["can_measured_sov"] is True
    assert plus_caps["can_api"] is False
    assert plus_caps["can_agency"] is False
    assert plus_caps["dash_plan"] == "plus"
    assert any(s["id"] == "measured_sov" for s in plus_caps["plan_services"])
    assert not any(s["id"] == "api_access" for s in plus_caps["plan_services"])

    assert biz_caps["can_api"] is True
    assert biz_caps["can_agency"] is True
    assert biz_caps["can_alerts"] is True
    assert biz_caps["dash_plan"] == "business"
    assert any(s["id"] == "api_access" for s in biz_caps["plan_services"])
    assert any(s["id"] == "agency_whitelabel" for s in biz_caps["plan_services"])


def test_dashboard_plan_theme_classes():
    with app.app_context():
        ensure_schema()
        free = _user("free")
        plus = _user("plus")
        business = _user("business")
        free_id, free_sv = free.id, int(free.session_version or 0)
        plus_id, plus_sv = plus.id, int(plus.session_version or 0)
        biz_id, biz_sv = business.id, int(business.session_version or 0)

    free_html = _client_for(free_id, free_sv).get("/dashboard").get_data(as_text=True)
    plus_html = _client_for(plus_id, plus_sv).get("/dashboard").get_data(as_text=True)
    biz_html = _client_for(biz_id, biz_sv).get("/dashboard").get_data(as_text=True)

    assert "dash-plan--free" in free_html
    assert 'data-dash-plan="free"' in free_html
    assert "Toolkit Free" in free_html
    assert 'href="/dashboard/storico"' not in free_html

    assert "dash-plan--plus" in plus_html
    assert 'data-dash-plan="plus"' in plus_html
    assert "Toolkit Plus" in plus_html
    assert "SoV measured" in plus_html
    assert 'href="/dashboard/storico"' in plus_html

    assert "dash-plan--business" in biz_html
    assert 'data-dash-plan="business"' in biz_html
    assert "Toolkit Business" in biz_html
    assert "White-label" in biz_html
    assert 'href="/dashboard/storico"' in biz_html


def test_settings_hides_unavailable_sections_per_plan():
    with app.app_context():
        ensure_schema()
        free = _user("free")
        plus = _user("plus")
        business = _user("business")
        free_id, free_sv = free.id, int(free.session_version or 0)
        plus_id, plus_sv = plus.id, int(plus.session_version or 0)
        biz_id, biz_sv = business.id, int(business.session_version or 0)

    free_html = _client_for(free_id, free_sv).get("/dashboard/impostazioni").get_data(
        as_text=True
    )
    plus_html = _client_for(plus_id, plus_sv).get("/dashboard/impostazioni").get_data(
        as_text=True
    )
    biz_html = _client_for(biz_id, biz_sv).get("/dashboard/impostazioni").get_data(
        as_text=True
    )

    assert "Alert outbound" not in free_html
    assert "Prompt bank" not in free_html
    assert "Genera nuova API key" not in free_html
    assert "White-label agenzia" not in free_html
    assert "Sblocca" not in free_html
    assert "Sicurezza account" in free_html

    assert "Alert outbound" in plus_html
    assert "Prompt bank" in plus_html
    assert "Genera nuova API key" not in plus_html
    assert "White-label agenzia" not in plus_html
    assert "Sblocca API" not in plus_html
    assert "Vedi piano" not in plus_html

    assert "Alert outbound" in biz_html
    assert "Prompt bank" in biz_html
    assert "Genera nuova API key" in biz_html
    assert "White-label agenzia" in biz_html


def test_dashboard_hides_upsells_for_free():
    with app.app_context():
        ensure_schema()
        free = _user("free")
        free_id, free_sv = free.id, int(free.session_version or 0)

    html = _client_for(free_id, free_sv).get("/dashboard").get_data(as_text=True)
    assert "pro-upsell" not in html
    assert "sblocca" not in html.lower()
    assert "White-label → Business" not in html
    assert "Passa a Plus" not in html
