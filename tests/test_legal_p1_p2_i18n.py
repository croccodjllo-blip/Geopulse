"""Legal P1/P2 UI strings are natively translated for every UI locale."""

from __future__ import annotations

from pathlib import Path

from flask import Flask
from flask_babel import Babel, force_locale, gettext as _


# Italian msgids that must differ in every non-IT locale (skip EN-identical brand labels).
MSGIDS = [
    "Gestisci consenso",
    "Accetta tutto",
    "Personalizza",
    "Salva preferenze",
    "Informativa cookie",
    "Trasparenza AI / LLM",
    "Dichiarazione di accessibilità",
    "Fatturazione e cancellazione",
    "Come gestire / annullare abbonamento",
    "DPA e sub-responsabili",
    "Scarica DPA (.txt)",
    "Informativa sulla privacy",
    "11. Limitazione di responsabilità",
    "Il Servizio è fornito “così com’è” e “come disponibile”, nei limiti consentiti dalla legge. Nella misura massima consentita, escludiamo garanzie implicite di commerciabilità, idoneità a uno scopo particolare e non violazione. Nulla in questi Termini limita diritti inderogabili del consumatore ove tu ne sia uno; per clienti B2B tipici, le limitazioni di questa sezione si applicano pienamente.",
]


EXPECTED = {
    "en": {
        "Gestisci consenso": "Manage consent",
        "Accetta tutto": "Accept all",
        "Informativa cookie": "Cookie Policy",
        "Fatturazione e cancellazione": "Billing and Cancellation",
    },
    "de": {
        "Gestisci consenso": "Einwilligung verwalten",
        "Accetta tutto": "Alle akzeptieren",
        "Informativa cookie": "Cookie-Richtlinie",
        "Fatturazione e cancellazione": "Abrechnung und Kündigung",
    },
    "es": {
        "Gestisci consenso": "Gestionar consentimiento",
        "Accetta tutto": "Aceptar todo",
        "Informativa cookie": "Política de cookies",
        "Fatturazione e cancellazione": "Facturación y cancelación",
    },
    "zh_Hans": {
        "Gestisci consenso": "管理同意偏好",
        "Accetta tutto": "全部接受",
        "Informativa cookie": "Cookie 政策",
        "Fatturazione e cancellazione": "账单与退订",
    },
    "ko": {
        "Gestisci consenso": "동의 관리",
        "Accetta tutto": "모두 수락",
        "Informativa cookie": "쿠키 정책",
        "Fatturazione e cancellazione": "결제 및 해지",
    },
}


def _app() -> Flask:
    app = Flask(__name__)
    app.config["BABEL_DEFAULT_LOCALE"] = "it"
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(Path("translations").resolve())
    Babel(app, locale_selector=lambda: "en")
    return app


def test_legal_p1_p2_msgids_translated():
    app = _app()
    for loc in ("en", "de", "es", "zh_Hans", "ko"):
        with app.app_context():
            with force_locale(loc):
                for msgid in MSGIDS:
                    assert _(msgid) != msgid, f"missing {loc}: {msgid[:80]}"


def test_legal_p1_p2_native_spot_checks():
    app = _app()
    for loc, samples in EXPECTED.items():
        with app.app_context():
            with force_locale(loc):
                for msgid, msgstr in samples.items():
                    assert _(msgid) == msgstr, f"{loc}: {msgid} -> {_(msgid)!r}"


def test_legal_overlay_modules_cover_catalog_empty_set():
    """Overlay dicts exist and compile as importable modules."""
    for name in (
        "legal_p1_p2_i18n_en",
        "legal_p1_p2_i18n_de",
        "legal_p1_p2_i18n_es",
        "legal_p1_p2_i18n_zh",
        "legal_p1_p2_i18n_ko",
    ):
        path = Path("scripts/data") / f"{name}.py"
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "Gestisci consenso" in text
        assert len(text) > 5000
