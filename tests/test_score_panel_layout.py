"""Score panel retired: pulse-core stack removed in favor of priority hero."""

from __future__ import annotations

from pathlib import Path


def test_score_panel_markup_retired():
    html = Path("templates/dashboard.html").read_text(encoding="utf-8")
    detail = Path("templates/partials/dash_sov_detail.html").read_text(encoding="utf-8")
    assert 'id="panel-score"' not in html
    assert "pulse-core__mast" not in html
    assert "signal-diag" not in html
    assert 'class="dash-hero"' in html
    # SoV table lives on /dashboard/sov via shared partial.
    assert 'id="panel-sov"' in detail


def test_pulse_core_css_may_remain_unused():
    """Legacy pulse CSS can linger; redesign must ship dash-hero rules."""
    css = Path("static/css/app.css").read_text(encoding="utf-8")
    assert ".dash-hero" in css
    assert "DASH REDESIGN 2026" in css
