"""Pack email popup strings are translated for every UI locale."""

from __future__ import annotations

from pathlib import Path

from flask import Flask
from flask_babel import Babel, force_locale, gettext as _


MSGIDS = [
    "Invia pack via email",
    "Indirizzo email",
    "Invia pack",
    "Inserisci l\u2019indirizzo email dove vuoi ricevere il pack HTML per questo dominio.",
    "Puoi inviarlo a te o a un collega. Limite giornaliero anti-abuso attivo.",
    "Pack inviato a %(email)s.",
]


def test_pack_mail_dialog_msgids_translated():
    app = Flask(__name__)
    app.config["BABEL_DEFAULT_LOCALE"] = "it"
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(
        Path("translations").resolve()
    )
    Babel(app, locale_selector=lambda: "en")
    for loc in ("en", "de", "es", "zh_Hans", "ko"):
        with app.app_context():
            with force_locale(loc):
                for msgid in MSGIDS:
                    assert _(msgid) != msgid, f"missing {loc}: {msgid}"


def test_pack_mail_lede_is_single_translatable_string():
    dash = Path("templates/dashboard.html").read_text(encoding="utf-8")
    assert "Inserisci l\u2019indirizzo email dove vuoi ricevere il pack HTML" in dash
    # Avoid brittle split phrases that break word order in other languages.
    assert "{{ _('per') }}" not in dash
