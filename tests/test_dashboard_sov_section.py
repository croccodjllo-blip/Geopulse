"""Dashboard SoV section: sidebar route + detail anteprima card."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
SOV = (ROOT / "templates" / "dashboard_sov.html").read_text(encoding="utf-8")
DETAIL = (ROOT / "templates" / "partials" / "dash_sov_detail.html").read_text(
    encoding="utf-8"
)
SIDEBAR = (ROOT / "templates" / "partials" / "app_topbar.html").read_text(
    encoding="utf-8"
)
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")


def test_sov_route_registered():
    assert 'def dashboard_sov(' in APP
    assert '"/dashboard/sov"' in APP


def test_sidebar_has_five_page_links():
    assert "dashboard_benchmark" in SIDEBAR
    assert "dashboard_prompt" in SIDEBAR
    assert "dashboard_trend" in SIDEBAR
    assert "{{ _('Panoramica') }}" in SIDEBAR


def test_main_dash_fold_without_sov_table():
    assert "dash-sov-list" not in DASH
    assert "dash_sov_detail.html" not in DASH
    assert "dash_signal.html" in DASH
    assert "dash_geo_charts.html" in (
        ROOT / "templates" / "partials" / "dash_signal.html"
    ).read_text(encoding="utf-8")


def test_sov_page_matches_detail_anteprima():
    assert "sov-page-hero" in SOV
    assert "bg-sov-anteprima.png" in SOV
    assert "dash_sov_detail.html" in SOV
    assert "sov_topnav.html" in SOV
    assert "body-dash--sov" in SOV
    assert "body-dash body-dash--sov" not in SOV  # avoid duplicate body-dash
    assert "dash-sov-list" not in DETAIL
    assert "dash_signal.html" in DETAIL
    assert "dash-finding-board" in DETAIL
    assert "dash-findings" in DETAIL
    assert "dash-cta__primary" in DETAIL
    assert "dash-cta--anteprima" in DETAIL
    assert ".sov-page-hero__accent" in CSS
    assert ".dash-detail--anteprima" in CSS
    assert ".sov-chrome__tab" in CSS
    assert "margin-inline: auto" in CSS
    assert "max-width: calc(100% - var(--sidebar-w)) !important" in CSS
    assert "body.body-dash:not(.body-dash--sov) .dash-sov .sov-ops" in CSS
    assert "token_balance_short" in APP
    assert (ROOT / "static" / "img" / "bg-sov-anteprima.png").is_file()
    nav = (ROOT / "templates" / "partials" / "sov_topnav.html").read_text(encoding="utf-8")
    assert "Panoramica" in nav
    assert "Benchmark" in nav
    assert "Prompt" in nav
    assert "Trends" in nav
    assert "Guida" in nav


def test_fold_sov_cta_visible():
    signal = (ROOT / "templates" / "partials" / "dash_signal.html").read_text(
        encoding="utf-8"
    )
    dash = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert "dash-kpis" in signal
    assert "dash_geo_charts.html" in signal
    assert "dash-audit" in CSS
