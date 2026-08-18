"""Unit tests for analyze-queue Sentry ops alerts."""

from __future__ import annotations

import centropic.ops_alerts as ops_alerts


def test_report_stale_running_jobs_skips_zero(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(ops_alerts, "_capture", lambda *a, **k: calls.append((a, k)))
    ops_alerts._STALE_LAST_TS = 0.0
    ops_alerts.report_stale_running_jobs(0, stale_after_minutes=5)
    assert calls == []


def test_report_stale_running_jobs_cooldown(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(ops_alerts, "_capture", lambda *a, **k: calls.append((a, k)))
    ops_alerts._STALE_LAST_TS = 0.0
    ops_alerts.report_stale_running_jobs(2, stale_after_minutes=5)
    ops_alerts.report_stale_running_jobs(3, stale_after_minutes=5)
    assert len(calls) == 1
    assert "analyze_stale_running" in calls[0][0][0]


def test_report_analyze_job_failed_forwards_extras(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(ops_alerts, "_capture", lambda *a, **k: calls.append((a, k)))
    ops_alerts.report_analyze_job_failed(
        job_id=42,
        user_id=7,
        error="boom",
        phase="sov",
    )
    assert len(calls) == 1
    msg, kwargs = calls[0][0][0], calls[0][1]
    assert "42" in msg
    assert kwargs["job_id"] == 42
    assert kwargs["user_id"] == 7
    assert kwargs["error"] == "boom"
    assert kwargs["progress_phase"] == "sov"


def test_capture_soft_fails_without_sentry(monkeypatch, caplog):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sentry_sdk":
            raise ImportError("no sentry")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with caplog.at_level("WARNING"):
        ops_alerts._capture("hello", level="error", job_id=1)
    assert any("no sentry sdk" in r.message for r in caplog.records)


def test_ops_alerts_never_raise():
    # Soft-fail contract: callers in app.py must not crash on alert path.
    ops_alerts.report_analyze_job_failed(
        job_id=1, user_id=None, error="x" * 600, phase=None
    )
    ops_alerts._STALE_LAST_TS = 0.0
    ops_alerts.report_stale_running_jobs(1, stale_after_minutes=5)
