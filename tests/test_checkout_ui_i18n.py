"""Native checkout/waiver UI strings must resolve in all supported locales."""

from __future__ import annotations

from flask_babel import force_locale

from app import app
from services.i18n import babel_locale

CHECKOUT_UI = [
    "Continua al pagamento",
    "Conferma obbligatoria prima del pagamento",
    "Paga Plus · 14,99€/mese",
    "Apri checkout / aggiorna pagamento",
    "Paga Business",
    "Spunta la casella per continuare.",
    "Apri DPA",
    "Checkout",
    "Analizza gratis",
    "Annulla",
    "Chiudi",
]

# App locale codes (zh → babel zh_Hans)
LOCALES = ("en", "de", "es", "zh", "ko")


def test_checkout_ui_translated_not_italian_fallback():
    with app.app_context():
        for loc in LOCALES:
            with force_locale(babel_locale(loc)):
                from flask_babel import gettext as _

                for msgid in CHECKOUT_UI:
                    out = _(msgid)
                    assert out, f"{loc}: empty for {msgid!r}"
                    # Must not fall back to Italian for these CTAs (except brand-identical).
                    if msgid not in {"Checkout"}:
                        assert out != msgid, f"{loc}: still Italian msgid {msgid!r}"


def test_empty_catalog_gaps_filled_all_locales():
    from babel.messages.pofile import read_po
    from pathlib import Path

    paths = {
        "en": Path("translations/en/LC_MESSAGES/messages.po"),
        "de": Path("translations/de/LC_MESSAGES/messages.po"),
        "es": Path("translations/es/LC_MESSAGES/messages.po"),
        "zh_Hans": Path("translations/zh_Hans/LC_MESSAGES/messages.po"),
        "ko": Path("translations/ko/LC_MESSAGES/messages.po"),
    }
    for loc, path in paths.items():
        po = read_po(path.open("rb"))
        empty = []
        for msg in po:
            if not msg.id:
                continue
            s = msg.string
            if isinstance(s, (list, tuple)):
                blank = not any(s)
            else:
                blank = not (s or "").strip()
            if blank:
                empty.append(msg.id)
        assert empty == [], f"{loc} still has empty msgstr: {empty[:5]}"
