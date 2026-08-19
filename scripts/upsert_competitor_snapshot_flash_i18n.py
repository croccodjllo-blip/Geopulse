#!/usr/bin/env python3
"""Upsert competitor-snapshot auto-fill flash gettext strings."""

from __future__ import annotations

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]

MSGID = "Competitor snapshot compilato in automatico: %(hosts)s"

TABLES = {
    "en": {
        MSGID: "Competitor snapshot auto-filled: %(hosts)s",
        "Competitor snapshot": "Competitor snapshot",
    },
    "de": {
        MSGID: "Competitor-Snapshot automatisch ergänzt: %(hosts)s",
        "Competitor snapshot": "Competitor-Snapshot",
    },
    "es": {
        MSGID: "Competitor snapshot completado automáticamente: %(hosts)s",
        "Competitor snapshot": "Competitor snapshot",
    },
    "ko": {
        MSGID: "Competitor snapshot 자동 작성: %(hosts)s",
        "Competitor snapshot": "Competitor snapshot",
    },
    "zh_Hans": {
        MSGID: "已自动填写 Competitor snapshot：%(hosts)s",
        "Competitor snapshot": "竞品快照",
    },
}


def upsert(catalog, msgid: str, msgstr: str) -> None:
    msg = catalog.get(msgid)
    if msg is None:
        catalog.add(msgid, msgstr, flags=[])
        return
    msg.string = msgstr
    if msg.flags:
        msg.flags.discard("fuzzy")


def main() -> None:
    for loc, table in TABLES.items():
        po_path = ROOT / "translations" / loc / "LC_MESSAGES" / "messages.po"
        with po_path.open("rb") as fh:
            cat = read_po(fh)
        for msgid, msgstr in table.items():
            upsert(cat, msgid, msgstr)
        with po_path.open("wb") as fh:
            write_po(fh, cat, ignore_obsolete=False, include_previous=False, width=80)
        with po_path.with_suffix(".mo").open("wb") as fh:
            write_mo(fh, cat)
        print(f"updated {po_path.relative_to(ROOT)} ({len(table)} strings)")


if __name__ == "__main__":
    main()
