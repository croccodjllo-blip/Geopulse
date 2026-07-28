"""Gates for measured SoV / citation monitor (Plus-only)."""

from __future__ import annotations

from types import SimpleNamespace

from services.sov_measured import should_run_measured, user_can_run_measured


def test_user_can_run_measured_plus_only():
    assert user_can_run_measured(None) is False
    assert user_can_run_measured(SimpleNamespace(is_pro=False)) is False
    assert user_can_run_measured(SimpleNamespace(is_pro=True)) is True


def test_should_run_measured_requires_plus_and_request(monkeypatch):
    monkeypatch.setattr(
        "services.sov_measured.measured_sov_available", lambda: True
    )
    free = SimpleNamespace(is_pro=False)
    plus = SimpleNamespace(is_pro=True)
    assert should_run_measured(user=free, requested=True, env_enabled=True) is False
    assert should_run_measured(user=plus, requested=False, env_enabled=True) is False
    assert should_run_measured(user=plus, requested=True, env_enabled=False) is False
    assert should_run_measured(user=plus, requested=True, env_enabled=True) is True


def test_geo_suite_skips_measured_for_free(monkeypatch):
    from services import geo_suite as gs

    called = {"n": 0}

    def _boom(**kwargs):
        called["n"] += 1
        return {"available": True, "findings": []}

    monkeypatch.setattr(gs, "run_citation_monitor", _boom)
    result = {
        "scraped": {"domain": "example.com", "entity": {}},
        "probes": {},
        "pages": [],
        "findings": [],
        "signals": {},
        "competitors": [],
    }
    # Even if run_measured=True, Free must not call the monitor.
    gs.run_geo_suite(
        result=result,
        user=SimpleNamespace(is_pro=False, company="Acme"),
        run_measured=True,
        prompts=["chi è acme?"],
    )
    assert called["n"] == 0
    assert "sov_measured" not in (result.get("signals") or {})
