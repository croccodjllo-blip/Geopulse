#!/usr/bin/env python3
"""Upsert native GEO Charts insights chrome gettext strings and compile .mo."""

from __future__ import annotations

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]

INSIGHTS_TITLE = "Insight GEO actionable"
INSIGHTS_EMPTY = "Nessun finding critico/warn nell'ultimo audit."
PAGES_SCORED = "Pagine valutate"
FINDINGS_LAST = "findings nell'ultimo audit"
IN_ORDINE = "In ordine"
DA_MONITORARE = "Da monitorare"
ELEVATA = "Elevata"
ALTA = "Alta"
INFO = "Info"

TABLES: dict[str, dict[str, str]] = {
    "en": {
        INSIGHTS_TITLE: "Actionable GEO Insights",
        INSIGHTS_EMPTY: "No critical/warn findings in the latest audit.",
        PAGES_SCORED: "Pages scored",
        FINDINGS_LAST: "findings in last audit",
        IN_ORDINE: "Clear",
        DA_MONITORARE: "Watch",
        ELEVATA: "Elevated",
        ALTA: "High",
        INFO: "Info",
        "Critico": "Critical",
        "Attenzione": "Warning",
    },
    "de": {
        INSIGHTS_TITLE: "Umsetzbare GEO-Insights",
        INSIGHTS_EMPTY: "Keine kritischen/Warn-Findings im letzten Audit.",
        PAGES_SCORED: "Bewertete Seiten",
        FINDINGS_LAST: "Findings im letzten Audit",
        IN_ORDINE: "In Ordnung",
        DA_MONITORARE: "Beobachten",
        ELEVATA: "Erhöht",
        ALTA: "Hoch",
        INFO: "Info",
        "Critico": "Kritisch",
        "Attenzione": "Warnung",
    },
    "es": {
        INSIGHTS_TITLE: "Insights GEO accionables",
        INSIGHTS_EMPTY: "Sin findings críticos/aviso en la última auditoría.",
        PAGES_SCORED: "Páginas evaluadas",
        FINDINGS_LAST: "findings en la última auditoría",
        IN_ORDINE: "En orden",
        DA_MONITORARE: "Vigilancia",
        ELEVATA: "Elevada",
        ALTA: "Alta",
        INFO: "Info",
        "Critico": "Crítico",
        "Attenzione": "Atención",
    },
    "ko": {
        INSIGHTS_TITLE: "실행 가능한 GEO 인사이트",
        INSIGHTS_EMPTY: "최근 감사에 심각/주의 파인딩이 없습니다.",
        PAGES_SCORED: "평가된 페이지",
        FINDINGS_LAST: "최근 감사의 파인딩",
        IN_ORDINE: "양호",
        DA_MONITORARE: "주시",
        ELEVATA: "높음",
        ALTA: "매우 높음",
        INFO: "정보",
        "Critico": "심각",
        "Attenzione": "주의",
    },
    "zh_Hans": {
        INSIGHTS_TITLE: "可执行的 GEO 洞察",
        INSIGHTS_EMPTY: "最近一次审计中无严重/警告发现。",
        PAGES_SCORED: "已评分页面",
        FINDINGS_LAST: "最近一次审计中的发现",
        IN_ORDINE: "正常",
        DA_MONITORARE: "关注",
        ELEVATA: "偏高",
        ALTA: "高",
        INFO: "信息",
        "Critico": "严重",
        "Attenzione": "警告",
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
        mo_path = po_path.with_suffix(".mo")
        with mo_path.open("wb") as fh:
            write_mo(fh, cat)
        print(f"updated {po_path.relative_to(ROOT)} ({len(table)} strings)")


if __name__ == "__main__":
    main()
