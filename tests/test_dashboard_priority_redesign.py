"""Dashboard priority redesign: preview rings, SoV list, no fold clutter."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
SHELL = (ROOT / "templates" / "partials" / "dashboard_shell.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "dash-preview.css").read_text(encoding="utf-8")
DYN = (ROOT / "templates" / "partials" / "dash_dynamic_styles.html").read_text(encoding="utf-8")


def test_preview_css_linked():
    assert "dash-preview.css" in DASH
    assert "head_extra" in DASH


def test_priority_hero_rings_and_micro_metrics():
    assert 'class="dash-hero"' in DASH
    assert "dash-ring--cvi" in DASH
    assert "dash-ring--sov" in DASH
    assert "dash-ring__svg" in DASH
    assert 'class="dash-micro"' in DASH
    assert "dash-actions__btn" in DASH
    assert "dash-sov-list" in DASH
    assert "dash-cta" in DASH


def test_score_sov_tabs_and_pulse_removed():
    assert 'data-tab="score"' not in DASH
    assert 'id="panel-score"' not in DASH
    assert "pulse-core" not in DASH
    assert "signal-diag" not in DASH
    assert "sov-columns" not in DASH
    assert "sov-table" not in DASH


def test_no_rail_and_solo_grid():
    assert "workspace-rail" not in DASH
    assert "workspace-grid--rail" not in DASH
    assert "workspace-strip--preview" in DASH


def test_analyze_below_fold_when_latest():
    assert "analyze_form.html" in DASH
    assert 'id="analyze-panel"' in DASH
    assert "analyze-reveal" not in SHELL
    assert "analyze_form.html" in SHELL  # empty-state path


def test_redesign_css_present():
    assert ".dash-ring__viz" in CSS
    assert ".dash-sov-list" in CSS
    assert ".dash-cta__primary" in CSS


def test_dynamic_styles_share_bars():
    assert "--share" in DYN
    assert "pulse-core" not in DYN
