"""Free included Stimato must run with a zero token wallet."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app import AnalysisJob, User, app, db, ensure_schema


def _preflight_ok(**kwargs):
    return SimpleNamespace(is_giant=False, required_cost_cents=25, message="")


def _cost(**kwargs):
    return SimpleNamespace(service_cost_eur_cents=25, breakdown=[])


def _session_user(*, plan: str, balance: int = 0) -> tuple:
    user = User(
        email=f"free-quota-{uuid4().hex}@example.com",
        name="Free Quota",
        plan=plan,
        credit_balance_cents=balance,
        credit_held_cents=0,
        email_verified_at=datetime.now(timezone.utc),
    )
    user.set_password("FreeQuota!234")
    db.session.add(user)
    db.session.commit()
    return user


def test_free_confirm_page_shows_start_with_zero_balance(monkeypatch):
    import app as app_mod

    monkeypatch.setattr(app_mod, "limiter", SimpleNamespace(allow=lambda *a, **k: True))
    monkeypatch.setattr(
        app_mod,
        "normalize_url",
        lambda u: u if str(u).startswith("http") else "https://" + str(u),
    )
    monkeypatch.setattr(app_mod, "check_page_word_budget", _preflight_ok)
    monkeypatch.setattr(app_mod, "estimate_analysis_cost", _cost)
    monkeypatch.setattr(app_mod, "MEASURED_SOV_ON_ANALYZE", False)

    with app.app_context():
        ensure_schema()
        app.config["WTF_CSRF_ENABLED"] = False
        user = _session_user(plan="free", balance=0)
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["session_version"] = int(getattr(user, "session_version", 0) or 0)

        resp = client.post(
            "/dashboard",
            data={"url": "https://free-quota.example/", "submit": "1"},
            follow_redirects=False,
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:800]
        html = resp.get_data(as_text=True)
        assert "Conferma e avvia analisi" in html
        assert "Copertura insufficiente" not in html
        assert 'action="' in html and "analyze/confirmed" in html


def test_free_confirm_enqueues_with_zero_balance(monkeypatch):
    monkeypatch.setenv("ASYNC_ANALYZE", "1")
    import app as app_mod

    monkeypatch.setattr(app_mod, "ASYNC_ANALYZE", True)
    monkeypatch.setattr(app_mod, "limiter", SimpleNamespace(allow=lambda *a, **k: True))
    monkeypatch.setattr(
        app_mod,
        "normalize_url",
        lambda u: u if str(u).startswith("http") else "https://" + str(u),
    )
    monkeypatch.setattr(app_mod, "check_page_word_budget", _preflight_ok)
    monkeypatch.setattr(app_mod, "estimate_analysis_cost", _cost)
    monkeypatch.setattr(app_mod, "kick_analyze_worker", lambda: None)
    monkeypatch.setattr("services.jobs._begin_immediate", lambda db_session: None)
    monkeypatch.setattr("services.usage_billing._begin_immediate", lambda db_session: None)
    monkeypatch.setattr(app_mod, "MEASURED_SOV_ON_ANALYZE", False)

    with app.app_context():
        ensure_schema()
        app.config["WTF_CSRF_ENABLED"] = False
        user = _session_user(plan="free", balance=0)
        uid = user.id
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = uid
            sess["session_version"] = int(getattr(user, "session_version", 0) or 0)

        resp = client.post(
            "/dashboard/analyze/confirmed",
            data={
                "url": "https://free-start.example/",
                "run_measured": "0",
                "competitors": "",
                "deep_crawl": "0",
                "cost_cents": "1",
                "ajax": "1",
            },
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:800]
        data = resp.get_json()
        assert data["ok"] is True
        job = db.session.get(AnalysisJob, data["job_id"])
        assert job is not None
        assert job.status in {"pending", "running"}
        assert int(getattr(job, "held_cents", 0) or 0) == 0
        db.session.refresh(user)
        assert int(user.credit_balance_cents or 0) == 0
        assert int(user.credit_held_cents or 0) == 0


def test_plus_zero_balance_still_blocked(monkeypatch):
    monkeypatch.setenv("ASYNC_ANALYZE", "1")
    import app as app_mod

    monkeypatch.setattr(app_mod, "ASYNC_ANALYZE", True)
    monkeypatch.setattr(app_mod, "limiter", SimpleNamespace(allow=lambda *a, **k: True))
    monkeypatch.setattr(
        app_mod,
        "normalize_url",
        lambda u: u if str(u).startswith("http") else "https://" + str(u),
    )
    monkeypatch.setattr(app_mod, "check_page_word_budget", _preflight_ok)
    monkeypatch.setattr(app_mod, "estimate_analysis_cost", _cost)
    monkeypatch.setattr(app_mod, "kick_analyze_worker", lambda: None)
    monkeypatch.setattr(app_mod, "MEASURED_SOV_ON_ANALYZE", False)

    with app.app_context():
        ensure_schema()
        app.config["WTF_CSRF_ENABLED"] = False
        user = _session_user(plan="plus", balance=0)
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["session_version"] = int(getattr(user, "session_version", 0) or 0)

        resp = client.post(
            "/dashboard/analyze/confirmed",
            data={
                "url": "https://plus-blocked.example/",
                "run_measured": "0",
                "competitors": "",
                "deep_crawl": "0",
                "cost_cents": "1",
                "ajax": "1",
            },
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        assert resp.status_code == 402
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "insufficient_credit"
        assert AnalysisJob.query.filter_by(user_id=user.id).count() == 0
