"""Dashboard CTAs: no toolkit strip; one pack download; one new-analysis entry."""

from __future__ import annotations

from pathlib import Path

DASH = Path("templates/dashboard.html").read_text(encoding="utf-8")
SIGNAL = Path("templates/partials/dash_signal.html").read_text(encoding="utf-8")
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
    assert "download_pack" not in SIGNAL
    assert "data-pack-mail-open" not in SIGNAL


def test_nuova_analisi_lives_in_analyze_reveal():
    assert 'class="dash-compose"' in DASH
    assert "dash-compose__title" in DASH
    assert "analyze-reveal" not in DASH
    assert "{{ _('Nuova analisi') }}" in DASH
    assert 'btn btn-ghost" href="#analyze"' not in SHELL
    assert 'btn btn-signal" href="#analyze"' not in SHELL
    assert "analyze_form.html" in SHELL or "analyze_form.html" in DASH
