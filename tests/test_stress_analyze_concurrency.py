"""Smoke tests for analyze concurrency stress harness helpers."""

from __future__ import annotations

from scripts.stress_analyze_concurrency import (
    STRESS_HOST,
    STRESS_SOURCE,
    _parse_ramp,
    _stress_url,
)


def test_parse_ramp_sorted_unique():
    assert _parse_ramp("32,8,16,8") == [8, 16, 32]
    assert _parse_ramp("") == []
    assert _parse_ramp("0,-1,5") == [5]


def test_stress_url_uses_safe_host():
    url = _stress_url("t", 3)
    assert url.startswith(f"https://{STRESS_HOST}/")
    assert "t" in url
    assert STRESS_SOURCE == "stress"
