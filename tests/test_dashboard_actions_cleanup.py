"""Dashboard CTAs: no toolkit strip; one pack download; one new-analysis entry."""

from __future__ import annotations

from pathlib import Path

DASH = Path("templates/dashboard.html").read_text(encoding="utf-8")
SHELL = Path("templates/partials/dashboard_shell.html").read_text(encoding="utf-8")


def test_toolkit_bar_removed():
    assert "plan-services" not in DASH
    assert "Toolkit Free" not in DASH
    assert "Toolkit Plus" not in DASH
    assert "Toolkit Business" not in DASH


def test_report_lead_button_soup_removed():
    assert "report-lead" not in SHELL
    assert "Scarica pack" not in SHELL
    assert "download_pack" not in SHELL


def test_single_pack_download_cta_in_deliverable():
    assert DASH.count("url_for('download_pack'") == 1
    assert "pack-deliverable__actions" in DASH
    assert "data-pack-mail-open" in DASH
    hero = DASH.split("dash-hero", 1)[1].split("dash-sov", 1)[0]
    assert "download_pack" not in hero
    assert "data-pack-mail-open" not in hero


def test_nuova_analisi_lives_in_analyze_reveal():
    assert 'class="analyze-reveal"' in SHELL
    assert "analyze-reveal__title" in SHELL
    assert "{{ _('Nuova analisi') }}" in SHELL
    assert 'btn btn-ghost" href="#analyze"' not in SHELL
    assert 'btn btn-signal" href="#analyze"' not in SHELL
