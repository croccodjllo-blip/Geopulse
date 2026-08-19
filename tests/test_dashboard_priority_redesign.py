"""Dashboard priority redesign: hero rings CVI+SoV, no Score/SoV tabs, no rail."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
SHELL = (ROOT / "templates" / "partials" / "dashboard_shell.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
DYN = (ROOT / "templates" / "partials" / "dash_dynamic_styles.html").read_text(encoding="utf-8")


def test_priority_hero_rings_and_micro_metrics():
    assert 'class="dash-hero"' in DASH
    assert "dash-ring--cvi" in DASH
    assert "dash-ring--sov" in DASH
    assert "dash-ring__svg" in DASH
    assert 'class="dash-micro"' in DASH
    assert 'class="dash-actions"' in DASH
    assert 'class="dash-sov"' in DASH


def test_score_sov_tabs_and_pulse_removed():
    assert 'data-tab="score"' not in DASH
    assert 'data-tab="sov"' not in DASH
    assert 'id="panel-score"' not in DASH
    assert "pulse-core" not in DASH
    assert "signal-diag" not in DASH
    assert "sov-columns" not in DASH
    assert "sov-hero__ring" not in DASH
    assert "sov-stack" not in DASH


def test_no_rail_and_solo_grid():
    assert "workspace-rail" not in DASH
    assert "workspace-grid--rail" not in DASH
    assert "workspace-grid--solo" in DASH


def test_sov_ops_once_not_in_shell():
    assert "sov_ops.html" not in SHELL
    assert DASH.count("partials/sov_ops.html") == 1


def test_actions_nav_has_priority_links():
    assert "{{ _('Nuova analisi') }}" in DASH
    assert "{{ _('Findings') }}" in DASH
    assert "{{ _('Edge') }}" in DASH
    assert "{{ _('Pack') }}" in DASH
    assert 'href="#analyze-panel"' in DASH
    assert "dash-actions__btn" in DASH


def test_redesign_css_present():
    assert "DASH REDESIGN 2026" in CSS
    assert ".dash-hero" in CSS
    assert ".dash-ring" in CSS
    assert ".dash-micro" in CSS
    assert ".dash-actions__btn" in CSS


def test_dynamic_styles_engine_only():
    assert "pulse-core" not in DYN
    assert "signal-diag" not in DYN
    assert "engine-bar" in DYN
