#!/usr/bin/env python3
"""Upsert dashboard UI gettext strings and compile .mo catalogs."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scripts" / "data"

LOCALES = {
    "en": (ROOT / "translations/en/LC_MESSAGES/messages.po", "EN", "dashboard_ui_i18n_en_de_es.py"),
    "de": (ROOT / "translations/de/LC_MESSAGES/messages.po", "DE", "dashboard_ui_i18n_en_de_es.py"),
    "es": (ROOT / "translations/es/LC_MESSAGES/messages.po", "ES", "dashboard_ui_i18n_en_de_es.py"),
    "zh": (ROOT / "translations/zh_Hans/LC_MESSAGES/messages.po", "ZH", "dashboard_ui_i18n_zh_ko.py"),
    "ko": (ROOT / "translations/ko/LC_MESSAGES/messages.po", "KO", "dashboard_ui_i18n_zh_ko.py"),
}


def load_table(module_file: str, attr: str) -> dict[str, str]:
    path = DATA / module_file
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    table = getattr(mod, attr)
    if not isinstance(table, dict):
        raise TypeError(f"{attr} in {path} must be dict")
    return table


def upsert(catalog, msgid: str, msgstr: str) -> None:
    msg = catalog.get(msgid)
    if msg is None:
        catalog.add(msgid, msgstr, flags=[])
        return
    msg.string = msgstr
    if msg.flags:
        msg.flags.discard("fuzzy")


def main() -> None:
    for short, (po_path, attr, module_file) in LOCALES.items():
        table = load_table(module_file, attr)
        with po_path.open("rb") as fh:
            cat = read_po(fh)
        for msgid, msgstr in table.items():
            upsert(cat, msgid, msgstr)
        with po_path.open("wb") as fh:
            write_po(fh, cat, ignore_obsolete=False, include_previous=False, width=80)
        mo_path = po_path.with_suffix(".mo")
        with mo_path.open("wb") as fh:
            write_mo(fh, cat)
        print(
            f"updated {po_path.relative_to(ROOT)} "
            f"({len(table)} strings) → {mo_path.name} [{short}]"
        )


if __name__ == "__main__":
    main()
