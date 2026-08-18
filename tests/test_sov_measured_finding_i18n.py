"""SoV measured warn finding + severity chrome are native (not Italian fallback)."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-sov-finding-i18n")

from flask_babel import force_locale, gettext as _

from app import app

TITLE = "SoV measured basso"
DETAIL = (
    "Poche menzioni brand nei prompt probe. Rafforza entity, llms.txt e "
    "contenuti citabili; amplia il prompt bank."
)

EXPECTED = {
    "en": {
        TITLE: "Low Measured SoV",
        DETAIL: (
            "Few brand mentions across the probe prompts. Strengthen entity "
            "signals, llms.txt, and citable content; expand your prompt bank."
        ),
        "Attenzione": "Warning",
        "Critico": "Critical",
    },
    "de": {
        TITLE: "Niedriger Measured SoV",
        "Attenzione": "Warnung",
    },
    "es": {
        TITLE: "SoV medido bajo",
        "Attenzione": "Atención",
    },
    "ko": {
        TITLE: "측정 SoV 낮음",
        "Attenzione": "주의",
    },
    "zh_Hans": {
        TITLE: "实测 SoV 偏低",
        "Attenzione": "警告",
    },
}


def test_sov_measured_finding_is_native():
    with app.app_context():
        for loc, pairs in EXPECTED.items():
            with force_locale(loc):
                for msgid, want in pairs.items():
                    got = _(msgid)
                    assert got == want, (loc, msgid, got, want)
                    assert got != msgid
                # Detail must not fall back to Italian for every locale.
                assert _(DETAIL) != DETAIL, loc
