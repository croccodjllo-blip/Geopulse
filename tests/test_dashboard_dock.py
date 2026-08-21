"""Workspace chrome is a top pill bar — no left dock."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDEBAR = (ROOT / "templates" / "partials" / "app_sidebar.html").read_text(
    encoding="utf-8"
)
TOPBAR = (ROOT / "templates" / "partials" / "app_topbar.html").read_text(
    encoding="utf-8"
)
BASE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
JS = (ROOT / "static" / "js" / "shell.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")


def test_topbar_has_pills_and_no_left_dock():
    assert "app_topbar.html" in SIDEBAR
    assert "app-topbar" in TOPBAR
    assert "app-topbar__pills" in TOPBAR
    assert "app-topbar__link" in TOPBAR
    assert "app-sidebar--dock" not in TOPBAR
    assert "data-dock-pin" not in TOPBAR
    assert "Fissa icone" not in TOPBAR
    assert "{{ _('Panoramica') }}" in TOPBAR
    assert "{{ _('Benchmark') }}" in TOPBAR
    assert "{{ _('Prompt') }}" in TOPBAR
    assert "{{ _('Trend') }}" in TOPBAR
    assert "{{ _('Guida') }}" in TOPBAR


def test_base_uses_topbar_not_sidebar_shell():
    assert "app_topbar.html" in BASE
    assert "app-shell--topbar" in BASE
    assert "app-shell--sidebar" not in BASE
    assert "app-topbar__link" in JS
    assert "topbar-open" in JS


def test_no_hidden_folds_on_main_dashboard():
    assert "<details" not in DASH
    assert "dash-more--ops" not in DASH
    assert "dash-deck" in DASH
    assert "dash-compose" in DASH
    assert "dash-meridian" in (
        ROOT / "templates" / "partials" / "dash_signal.html"
    ).read_text(encoding="utf-8")
    assert "edge-advanced--open" in (
        ROOT / "templates" / "partials" / "dash_prompt_ops.html"
    ).read_text(encoding="utf-8")


def test_topbar_css_clears_left_offset():
    assert ".app-topbar" in CSS
    assert ".app-topbar__link.is-active" in CSS
    assert "body.app-shell--topbar .site-main" in CSS
    assert "margin-left: 0 !important" in CSS


def test_dash_canvas_is_flush_and_warm():
    assert "dash-signal" in CSS
    assert "Compact flush canvas" in CSS
    assert "Signal deck" in CSS
    assert "Synthex" in CSS
    assert "#3FA8B5" not in CSS.split("Compact flush canvas")[-1]
    assert "#C9D3DD" not in CSS.split("Compact flush canvas")[-1]
    assert "#8B5CF6" not in CSS.split("Signal deck")[-1]
