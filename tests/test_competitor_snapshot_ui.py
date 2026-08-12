"""Competitor snapshot is a graphic arena, not a plain text list."""

from __future__ import annotations

from pathlib import Path


def test_competitor_snapshot_partial_is_graphic_and_csp_safe():
    partial = Path("templates/partials/competitor_snapshot.html").read_text(
        encoding="utf-8"
    )
    assert 'class="comp-arena' in partial
    assert "comp-card__chart" in partial
    assert 'data-fill' in partial
    assert 'nonce="{{ csp_nonce }}"' in partial
    assert "style=" not in partial.replace("stroke-", "")
    # No HTML style= attributes (CSP style-src-attr none).
    assert ' style="' not in partial
    assert "style='" not in partial


def test_dashboard_includes_competitor_snapshot_partial():
    dash = Path("templates/dashboard.html").read_text(encoding="utf-8")
    assert 'partials/competitor_snapshot.html' in dash
    assert "comp-list" not in dash.split('id="edge-signals"')[0]


def test_comp_arena_css_present():
    css = Path("static/css/app.css").read_text(encoding="utf-8")
    assert ".comp-arena" in css
    assert ".comp-card__track [data-fill]" in css
    assert ".comp-card__mark" in css
