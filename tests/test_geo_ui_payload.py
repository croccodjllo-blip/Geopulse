"""GEO UI live payload shape."""

from __future__ import annotations

from services.geo_ui_payload import _engine_status, _insight_severity


def test_engine_status_thresholds():
    assert _engine_status(None) == "unknown"
    assert _engine_status(50) == "dominant"
    assert _engine_status(35) == "optimal"
    assert _engine_status(10) == "needs_action"


def test_insight_severity_map():
    assert _insight_severity("critical") == "high"
    assert _insight_severity("warn") == "gap"
    assert _insight_severity("ok") == "info"
