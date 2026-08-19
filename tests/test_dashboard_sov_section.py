"""Dashboard SoV section: sidebar route + detail anteprima card."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
SOV = (ROOT / "templates" / "dashboard_sov.html").read_text(encoding="utf-8")
DETAIL = (ROOT / "templates" / "partials" / "dash_sov_detail.html").read_text(
    encoding="utf-8"
)
SIDEBAR = (ROOT / "templates" / "partials" / "app_sidebar.html").read_text(
    encoding="utf-8"
)
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")


def test_sov_route_registered():
    assert 'def dashboard_sov(' in APP
    assert '"/dashboard/sov"' in APP


def test_sidebar_has_sov_link():
    assert "dashboard_sov" in SIDEBAR
    assert 'nav == \'sov\'' in SIDEBAR or 'nav == "sov"' in SIDEBAR


def test_main_dash_fold_without_sov_table():
    assert "dash-sov-list" not in DASH
    assert "dash_sov_detail.html" not in DASH
    assert 'class="dash-hero"' in DASH
    assert "dashboard_sov" in DASH  # deep-link from ghosts


def test_sov_page_matches_detail_anteprima():
    assert "sov-page-hero" in SOV
    assert "bg-sov-anteprima.png" in SOV
    assert "dash_sov_detail.html" in SOV
    assert "dash-sov-list" in DETAIL
    assert "dash-sov-list__mark" in DETAIL
    assert "dash-findings" in DETAIL
    assert "dash-cta__primary" in DETAIL
    assert "dash-cta--anteprima" in DETAIL
    assert "Ultimi 28 giorni" in DETAIL
    assert "_('Avviso')" in DETAIL
    assert ".sov-page-hero__accent" in CSS
    assert ".dash-detail--anteprima" in CSS
    assert (ROOT / "static" / "img" / "bg-sov-anteprima.png").is_file()
