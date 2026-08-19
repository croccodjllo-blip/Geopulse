#!/usr/bin/env python3
"""Upsert multi-site dashboard gettext strings and compile .mo catalogs."""

from __future__ import annotations

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]

# Italian msgids (source language) → native msgstr per locale.
TABLES: dict[str, dict[str, str]] = {
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
        "Report completo": "Vollständiger Report",
        "siti nel workspace": "Websites im Workspace",
        "Apri report": "Report öffnen",
        "Report completo per dominio: score, SoV, findings, Edge e pack.": (
            "Vollständiger Report pro Domain: Score, SoV, Findings, Edge und Pack."
        ),
        "Upgrade a Plus per monitorare più domini nello stesso workspace.": (
            "Upgrade auf Plus, um mehr Domains im selben Workspace zu überwachen."
        ),
    },
    "es": {
        "Cambia sito": "Cambiar sitio",
        "Sito attivo": "Sitio activo",
        "Report completo": "Informe completo",
        "siti nel workspace": "sitios en el workspace",
        "Apri report": "Abrir informe",
        "Report completo per dominio: score, SoV, findings, Edge e pack.": (
            "Informe completo por dominio: score, SoV, findings, Edge y pack."
        ),
        "Upgrade a Plus per monitorare più domini nello stesso workspace.": (
            "Mejora a Plus para monitorizar más dominios en el mismo workspace."
        ),
    },
    "ko": {
        "Cambia sito": "사이트 전환",
        "Sito attivo": "활성 사이트",
        "Report completo": "전체 리포트",
        "siti nel workspace": "워크스페이스 사이트",
        "Apri report": "리포트 열기",
        "Report completo per dominio: score, SoV, findings, Edge e pack.": (
            "도메인별 전체 리포트: score, SoV, findings, Edge 및 pack."
        ),
        "Upgrade a Plus per monitorare più domini nello stesso workspace.": (
            "같은 워크스페이스에서 더 많은 도메인을 모니터링하려면 Plus로 업그레이드하세요."
        ),
    },
    "zh_Hans": {
        "Cambia sito": "切换站点",
        "Sito attivo": "当前站点",
        "Report completo": "完整报告",
        "siti nel workspace": "工作区站点",
        "Apri report": "打开报告",
        "Report completo per dominio: score, SoV, findings, Edge e pack.": (
            "每个域名的完整报告：评分、SoV、findings、Edge 与 pack。"
        ),
        "Upgrade a Plus per monitorare più domini nello stesso workspace.": (
            "升级到 Plus，即可在同一工作区监控更多域名。"
        ),
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
