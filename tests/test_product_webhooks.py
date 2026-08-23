"""analysis.completed + pack.ready fire without regression findings."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from services.alerts import dispatch_run_events
from services.api_metrics import analysis_completed_payload


def test_dispatch_run_events_sends_completed_and_pack_ready():
    user = SimpleNamespace(
        id=1,
        is_admin=False,
        is_pro=True,
        plan="plus",
        webhook_url="https://hooks.example.com/centropic",
        webhook_secret="",
    )
    site = SimpleNamespace(
        id=9,
        url="https://example.com/",
        domain="example.com",
        aio_score=81,
        geo_score=74,
        findings=[],
        signals={},
        llms_txt="# brand",
        json_ld_artifact="",
        robots_artifact="",
        signals_hosted=False,
        public_token=None,
        signals_version=2,
        updated_at=None,
    )
    captured: list[dict] = []

    def _fake_deliver(*, url, secret, payload, timeout=12):
        captured.append(payload)
        return {"ok": True, "status": 204}

    with patch("services.alerts.deliver_webhook", side_effect=_fake_deliver):
        with patch("services.alerts._user_may_dispatch_alerts", return_value=True):
            out = dispatch_run_events(
                user=user,
                site=site,
                public_base="https://centropic.ai",
                edge_full=True,
                run_id=44,
                source="api",
            )
    assert out["completed"]["ok"] is True
    assert out["pack"]["ok"] is True
    events = [p["event"] for p in captured]
    assert events == ["analysis.completed", "pack.ready"]
    completed = captured[0]
    assert completed["scores"]["aio"] == 81
    assert "# brand" not in str(completed)
    pack = captured[1]
    assert pack["idempotency_key"] == "9:2"
    assert "checksums" in pack
    assert pack["checksums"]["llms.txt"]


def test_dispatch_run_events_skips_without_url():
    user = SimpleNamespace(id=1, is_pro=True, plan="plus", webhook_url="")
    site = SimpleNamespace(id=1, findings=[], aio_score=1, geo_score=1)
    out = dispatch_run_events(user=user, site=site)
    assert out["skipped"] == "no_url"


def test_analysis_completed_payload_has_stable_event_id():
    site = SimpleNamespace(
        id=3,
        url="https://example.com/",
        domain="example.com",
        aio_score=50,
        geo_score=50,
        findings=[],
        signals={},
        llms_txt="",
        json_ld_artifact="",
        robots_artifact="",
        signals_hosted=False,
        public_token=None,
        signals_version=1,
        updated_at=None,
    )
    payload = analysis_completed_payload(site, run_id=7, source="scheduled")
    assert payload["event"] == "analysis.completed"
    assert payload["event_id"] == "analysis.completed:3:7:1"
    assert payload["source"] == "scheduled"
