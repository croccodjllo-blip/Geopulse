"""Multi-site dashboard chrome uses native gettext (not raw Italian)."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-multi-site-i18n")

from flask_babel import force_locale, gettext as _

from app import app

STRINGS = (
    "Cambia sito",
    "Sito attivo",
    "Report completo",
    "siti nel workspace",
    "Apri report",
    "Report completo per dominio: score, SoV, findings, Edge e pack.",
    "Upgrade a Plus per monitorare più domini nello stesso workspace.",
)

EXPECT = {
    "en": {
        "Cambia sito": "Switch site",
        "Sito attivo": "Active site",
        "Report completo": "Full report",
        "siti nel workspace": "sites in workspace",
        "Apri report": "Open report",
        "Report completo per dominio: score, SoV, findings, Edge e pack.": (
            "Full report per domain: score, SoV, findings, Edge and pack."
        ),
        "Upgrade a Plus per monitorare più domini nello stesso workspace.": (
            "Upgrade to Plus to monitor more domains in the same workspace."
        ),
    },
    "de": {
        "Cambia sito": "Website wechseln",
        "Sito attivo": "Aktive Website",
        "Apri report": "Report öffnen",
    },
    "es": {
        "Cambia sito": "Cambiar sitio",
        "Sito attivo": "Sitio activo",
        "Apri report": "Abrir informe",
    },
    "ko": {
        "Cambia sito": "사이트 전환",
        "Sito attivo": "활성 사이트",
        "Apri report": "리포트 열기",
    },
    "zh_Hans": {
        "Cambia sito": "切换站点",
        "Sito attivo": "当前站点",
        "Apri report": "打开报告",
    },
}


def test_multi_site_dashboard_strings_native():
    with app.app_context():
        for loc, table in EXPECT.items():
            with force_locale(loc):
                for msgid, want in table.items():
                    got = _(msgid)
                    assert got == want, f"{loc}: {msgid!r} → {got!r} (want {want!r})"
                # Italian source must not leak for translated chrome labels
                assert _("Sito attivo") != "Sito attivo"
                assert _("Apri report") != "Apri report"
                assert "monitorare" not in _(
                    "Upgrade a Plus per monitorare più domini nello stesso workspace."
                )
        with force_locale("en"):
            for msgid in STRINGS:
                assert _(msgid) != msgid
