"""Signal dock: readable labels by default, pin collapses to icons."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDEBAR = (ROOT / "templates" / "partials" / "app_sidebar.html").read_text(
    encoding="utf-8"
)
BASE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
JS = (ROOT / "static" / "js" / "shell.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")


def test_dock_has_readable_labels_and_pin():
    assert "app-sidebar--dock" in SIDEBAR
    assert "app-sidebar--rail" not in SIDEBAR
    assert "app-sidebar__link-label" in SIDEBAR
    assert "data-dock-pin" in SIDEBAR
    assert "Fissa icone" in SIDEBAR
    assert "Apri menu" in SIDEBAR
    assert "app-sidebar__idx" in SIDEBAR
    assert "{{ _('Dashboard') }}" in SIDEBAR
    assert "{{ _('Share of Voice') }}" in SIDEBAR
    assert "{{ _('Impostazioni') }}" in SIDEBAR


def test_dock_persists_before_paint():
    assert 'data-dock="open"' in BASE
    assert "centropic.dock" in BASE
    assert "localStorage.getItem" in BASE
    assert "applyDock" in JS
    assert 'localStorage.setItem("centropic.dock"' in JS


def test_no_hidden_folds_on_main_dashboard():
    assert "<details" not in DASH
    assert "dash-more--ops" not in DASH
    assert "dash-deck" in DASH
    assert "dash-compose" in DASH
    assert "dash-meridian" in (
        ROOT / "templates" / "partials" / "dash_signal.html"
    ).read_text(encoding="utf-8")
    assert "edge-advanced--open" in DASH


def test_dock_css_has_open_and_rail_widths():
    assert "--sidebar-w: 14.75rem" in CSS
    assert 'html[data-dock="rail"]' in CSS
    assert ".app-sidebar__pin" in CSS


def test_dash_canvas_is_flush_and_warm():
    assert "dash-signal" in CSS
    assert "Compact flush canvas" in CSS
    assert "Signal deck" in CSS
    assert "#3FA8B5" not in CSS.split("Compact flush canvas")[-1]
    assert "#C9D3DD" not in CSS.split("Compact flush canvas")[-1]
    assert "#8B5CF6" not in CSS.split("Signal deck")[-1]
