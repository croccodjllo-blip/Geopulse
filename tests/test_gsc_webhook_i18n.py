"""Settings webhook + GSC connector strings are native gettext."""

from __future__ import annotations

from pathlib import Path

from babel.messages.pofile import read_po

ROOT = Path(__file__).resolve().parents[1]

MSGIDS = (
    "Opzionale. Salvato cifrato a riposo; non viene mai rimostrato in chiaro dopo il salvataggio.",
    "Pronto per il collegamento OAuth",
    "Collega Google Search Console (sola lettura) per questo account.",
    "Collega Google",
    "Secret già impostato (cifrato a riposo). Lascia vuoto per mantenerlo; scrivi “clear” per rimuoverlo.",
)


def test_gsc_webhook_i18n_native():
    for loc, sample in (
        ("en", "Optional. Stored encrypted"),
        ("de", "Optional. Verschlüsselt"),
        ("es", "Opcional. Guardado cifrado"),
        ("ko", "선택 사항"),
        ("zh_Hans", "可选。静态加密"),
    ):
        po = ROOT / "translations" / loc / "LC_MESSAGES" / "messages.po"
        cat = read_po(po.open("rb"))
        msg = cat.get(MSGIDS[0])
        assert msg is not None, loc
        assert msg.string, loc
        assert sample in (msg.string or ""), (loc, msg.string)
        ready = cat.get(MSGIDS[1])
        assert ready is not None and ready.string, loc
        assert MSGIDS[1] not in (ready.string or "") or loc == "it"
        note = cat.get(MSGIDS[2])
        assert note is not None and note.string, loc
        assert "Collega Google Search Console" not in (note.string or "") or loc.startswith(
            "it"
        )


def test_gsc_py_uses_gettext():
    src = Path("services/gsc.py").read_text(encoding="utf-8")
    assert "from flask_babel import gettext as _" in src
    assert "Pronto per il collegamento OAuth" in src
    assert "Collega Google Search Console (sola lettura) per questo account." in src
    assert "_(" in src
