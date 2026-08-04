"""Scheduled rescan must claim exclusively and refuse free measured SoV."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.rescan import process_due_rescans


def test_process_due_rescans_skips_when_claim_loses(monkeypatch):
    monkeypatch.setattr("services.rescan.claim_due_site", lambda *a, **k: False)
    monkeypatch.setattr(
        "services.rescan.run_analysis_pipeline",
        lambda **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    site = SimpleNamespace(
        id=3,
        user_id=1,
        url="https://example.com/",
        next_rescan_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    user = SimpleNamespace(id=1, is_pro=True)

    class _Due:
        def limit(self, n):
            return self

        def all(self):
            return [site]

    monkeypatch.setattr("services.rescan.due_sites_query", lambda *a, **k: _Due())
    db = MagicMock()
    db.get.return_value = user

    stats = process_due_rescans(
        db_session=db,
        SiteAnalysis=MagicMock(),
        AnalysisRun=MagicMock(),
        User=MagicMock(),
        measured=False,
    )
    assert stats["skipped"] == 1
    assert stats["ok"] == 0


def test_process_due_rescans_disables_measured_without_billing(monkeypatch):
    calls = {}

    def fake_pipeline(**kwargs):
        calls["run_measured"] = kwargs.get("run_measured")
        calls["usage_callback"] = kwargs.get("usage_callback")
        return MagicMock()

    monkeypatch.setattr("services.rescan.run_analysis_pipeline", fake_pipeline)
    monkeypatch.setattr("services.rescan.claim_due_site", lambda *a, **k: True)

    user = SimpleNamespace(id=1, is_pro=True)
    site = SimpleNamespace(
        id=3,
        user_id=1,
        url="https://example.com/",
        next_rescan_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    class _Due:
        def limit(self, n):
            return self

        def all(self):
            return [site]

    monkeypatch.setattr("services.rescan.due_sites_query", lambda *a, **k: _Due())

    db = MagicMock()
    db.get.side_effect = lambda model, pk: user if pk == 1 else site

    stats = process_due_rescans(
        db_session=db,
        SiteAnalysis=MagicMock(),
        AnalysisRun=MagicMock(),
        User=MagicMock(),
        measured=True,
        usage_callback=None,
    )
    assert stats["ok"] == 1
    assert calls["run_measured"] is False
    assert calls["usage_callback"] is None
