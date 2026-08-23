"""Phone layout: nav drawer, readable KPIs, no 7-up crush at 390px."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS3 = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
APP = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
BASE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
JS = (ROOT / "static" / "js" / "shell.js").read_text(encoding="utf-8")


def test_marketing_header_has_phone_toggle():
    assert 'data-nav-toggle' in BASE
    assert 'id="site-nav"' in BASE
    assert "site-header__toggle" in APP
    assert "body.nav-open .nav-links" in APP
    assert "setNavOpen" in JS
    assert "data-nav-toggle" in JS


def test_phone_kpis_are_two_columns():
    phone = CSS3.split("PHONE 390")[-1]
    assert "max-width: 640px" in phone
    assert "repeat(2, minmax(0, 1fr))" in phone
    assert "repeat(7, minmax(0, 1fr))" in CSS3


def test_phone_stacks_cvi_and_full_width_audit():
    phone = CSS3.split("PHONE 390")[-1]
    assert "dash-masthead" in phone
    assert "grid-template-columns: 1fr" in phone
    assert "dash-command__search" in phone
    assert "width: 100%" in phone
    assert "6.8rem" in phone


def test_phone_does_not_lock_dash_viewport():
    phone = CSS3.split("PHONE 390")[-1]
    assert "overflow: visible" in phone
    locked = {line.strip() for line in CSS3.splitlines()}
    assert "height: 100vh;" not in locked
    assert "height: 100dvh;" not in locked
