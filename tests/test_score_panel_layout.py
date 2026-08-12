"""Score panel is one vertical composition: intro → mast → full-width table."""

from __future__ import annotations

from pathlib import Path


def test_score_panel_markup_is_stacked_not_split():
    html = Path("templates/dashboard.html").read_text(encoding="utf-8")
    start = html.find('id="panel-score"')
    end = html.find('id="panel-sov"')
    assert start != -1 and end != -1 and start < end
    chunk = html[start:end]
    assert 'class="pulse-core__intro"' in chunk
    assert 'class="pulse-core__mast"' in chunk
    assert 'class="pulse-core__stats"' in chunk
    assert 'class="signal-diag"' in chunk
    assert "pulse-core__intel" not in chunk
    # Mast appears before the diagnostics table (stacked reading order).
    assert chunk.find("pulse-core__mast") < chunk.find('class="signal-diag"')


def test_pulse_core_css_drops_side_by_side_split():
    css = Path("static/css/app.css").read_text(encoding="utf-8")
    assert ".pulse-core__mast" in css
    assert ".pulse-core__stats" in css
    # Legacy two-column Score split removed.
    assert "minmax(280px, 0.95fr) minmax(0, 1.15fr)" not in css
