"""Desktop sidebar can hide; the page width follows --sidebar-w."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_base_persists_sidebar_before_paint():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'data-sidebar="open"' in base
    assert "centropic.sidebar" in base
    assert 'nonce="{{ csp_nonce }}"' in base
    assert "data-sidebar-toggle" in base
    assert "data-label-close" in base
    assert "data-label-open" in base


def test_landing_still_loads_preview_css():
    landing = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "css/site-preview-v3.css" in landing
    assert "css/site-preview-v3.css" not in base


def test_css_sidebar_width_follows_html_state():
    css = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert "html[data-sidebar=\"hidden\"]" in css
    assert "--sidebar-w: 0px" in css
    assert "margin-left: var(--sidebar-w)" in css
    assert "width: calc(100% - var(--sidebar-w))" in css
    assert "html[data-sidebar=\"hidden\"] .app-sidebar" in css


def test_shell_hides_sidebar_on_desktop_and_draws_on_mobile():
    js = (ROOT / "static" / "js" / "shell.js").read_text(encoding="utf-8")
    assert "centropic.sidebar" in js
    assert "persistDesktop" in js
    assert "setMobileOpen" in js
    assert "max-width: 960px" in js
    assert "activateReportView" in js
