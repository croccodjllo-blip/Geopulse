"""Marketing homepage carries preview brand lockup + site chrome CSS."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_landing_preview_lockup():
    html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "hero-brand-lockup--preview" in html
    assert "CENTROPIC" in html
    assert "logo.svg" in html


def test_base_loads_preview_css_sitewide():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "css/dash-preview.css" in base
    # Must not be wrapped only for logged-in users.
    chunk = base.split("dash-preview.css", 1)[0][-200:]
    assert "current_user" not in chunk


def test_marketing_css_targets_body_marketing():
    css = (ROOT / "static" / "css" / "dash-preview.css").read_text(encoding="utf-8")
    assert "body.body-marketing" in css
    assert "hero-brand-lockup--preview" in css
    assert "SITE-WIDE marketing" in css


def test_guide_dashboard_svg_shows_rings():
    svg = (ROOT / "static" / "img" / "guide" / "dashboard.svg").read_text(encoding="utf-8")
    assert "Share of Voice" in svg
    assert "Centropic Visibility Index" in svg
    assert "circle" in svg
