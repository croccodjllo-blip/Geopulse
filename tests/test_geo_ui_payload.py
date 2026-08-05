"""GEO UI live payload shape."""

from __future__ import annotations

from services.geo_ui_payload import (
    _engine_status,
    _insight_severity,
    _issue_pressure,
)
from services.engine_breakdown import apply_measured_sov, compute_engine_breakdown


def test_engine_status_thresholds():
    assert _engine_status(None) == "unknown"
    assert _engine_status(50) == "dominant"
    assert _engine_status(35) == "optimal"
    assert _engine_status(10) == "needs_action"


def test_insight_severity_preserves_critical_and_warn():
    assert _insight_severity("critical") == "critical"
    assert _insight_severity("warn") == "warn"
    assert _insight_severity("warning") == "warn"
    assert _insight_severity("ok") == "info"


def test_issue_pressure_is_open_finding_count():
    assert _issue_pressure(0) == (0, "Clear")
    assert _issue_pressure(2) == (2, "Watch")
    assert _issue_pressure(4) == (4, "Elevated")
    assert _issue_pressure(9) == (9, "High")


def test_measured_overlay_hides_pending_but_keeps_unavailable():
    breakdown = compute_engine_breakdown(
        aio_score=60,
        geo_score=55,
        findings=[],
        robots_text="",
    )
    measured = {
        "available": True,
        "brand_mention_rate": 40,
        "engines": [
            {
                "id": "openai",
                "evidence": "measured",
                "mention_rate": 40,
                "samples": 3,
            },
            {
                "id": "google",
                "evidence": "pending",
                "mention_rate": None,
                "reason": "Configura Gemini",
            },
            {
                "id": "anthropic",
                "evidence": "unavailable",
                "mention_rate": None,
                "reason": "Quota esaurita",
            },
        ],
    }

    out = apply_measured_sov(breakdown, measured)
    engines = {engine["id"]: engine for engine in out["engines"]}
    assert "google" not in engines
    assert engines["anthropic"]["evidence"] == "unavailable"
    assert engines["anthropic"]["reason"] == "Quota esaurita"
