#!/usr/bin/env python3
"""Upsert native re-measure / first-diagnosis confirm copy and compile .mo."""

from __future__ import annotations

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]

TABLES: dict[str, dict[str, str]] = {
    "en": {
        "Ri-misurazione": "Re-measurement",
        "Prima diagnosi": "First diagnosis",
        "Crawl fino a %(n)s pagine. ": "Crawl up to %(n)s pages. ",
        "Include probe SoV Misurato (Plus). ": (
            "Includes Measured SoV probes (Plus). "
        ),
        "Ricalcola score e findings dopo eventuali fix pubblicati. Gli score possono salire o scendere — non è un miglioramento garantito.": (
            "Recalculates scores and findings after any published fixes. "
            "Scores may go up or down — improvement is not guaranteed."
        ),
        "Misura i segnali pubblici attuali e produce score AIO/GEO, findings e pack. Non prevede un guadagno di score: il risultato dipende dal sito.": (
            "Measures current public signals and produces AIO/GEO scores, findings, and a pack. "
            "It does not promise a higher score: the outcome depends on the site."
        ),
    },
    "de": {
        "Ri-misurazione": "Neuvermessung",
        "Prima diagnosi": "Erste Diagnose",
        "Crawl fino a %(n)s pagine. ": "Crawl von bis zu %(n)s Seiten. ",
        "Include probe SoV Misurato (Plus). ": (
            "Inklusive Measured-SoV-Probes (Plus). "
        ),
        "Ricalcola score e findings dopo eventuali fix pubblicati. Gli score possono salire o scendere — non è un miglioramento garantito.": (
            "Berechnet Scores und Findings nach veröffentlichten Fixes neu. "
            "Scores können steigen oder sinken — eine Verbesserung ist nicht garantiert."
        ),
        "Misura i segnali pubblici attuali e produce score AIO/GEO, findings e pack. Non prevede un guadagno di score: il risultato dipende dal sito.": (
            "Misst die aktuellen öffentlichen Signale und erzeugt AIO/GEO-Scores, Findings und ein Pack. "
            "Kein versprochener Score-Gewinn: das Ergebnis hängt von der Website ab."
        ),
    },
    "es": {
        "Ri-misurazione": "Nueva medición",
        "Prima diagnosi": "Primera diagnosis",
        "Crawl fino a %(n)s pagine. ": "Crawl de hasta %(n)s páginas. ",
        "Include probe SoV Misurato (Plus). ": (
            "Incluye sondas de SoV medido (Plus). "
        ),
        "Ricalcola score e findings dopo eventuali fix pubblicati. Gli score possono salire o scendere — non è un miglioramento garantito.": (
            "Recalcula puntuaciones y findings tras los fixes publicados. "
            "Las puntuaciones pueden subir o bajar: no hay mejora garantizada."
        ),
        "Misura i segnali pubblici attuali e produce score AIO/GEO, findings e pack. Non prevede un guadagno di score: il risultato dipende dal sito.": (
            "Mide las señales públicas actuales y genera puntuaciones AIO/GEO, findings y un pack. "
            "No promete una subida de score: el resultado depende del sitio."
        ),
    },
    "ko": {
        "Ri-misurazione": "재측정",
        "Prima diagnosi": "첫 진단",
        "Crawl fino a %(n)s pagine. ": "최대 %(n)s페이지까지 크롤합니다. ",
        "Include probe SoV Misurato (Plus). ": (
            "Measured SoV 프로브를 포함합니다(Plus). "
        ),
        "Ricalcola score e findings dopo eventuali fix pubblicati. Gli score possono salire o scendere — non è un miglioramento garantito.": (
            "게시된 수정 사항을 반영해 점수와 findings를 다시 계산합니다. "
            "점수는 오를 수도 내릴 수도 있으며, 향상이 보장되지 않습니다."
        ),
        "Misura i segnali pubblici attuali e produce score AIO/GEO, findings e pack. Non prevede un guadagno di score: il risultato dipende dal sito.": (
            "현재 공개 시그널을 측정하고 AIO/GEO 점수, findings, 팩을 생성합니다. "
            "점수 상승을 약속하지 않으며, 결과는 사이트에 따라 달라집니다."
        ),
    },
    "zh_Hans": {
        "Ri-misurazione": "重新测量",
        "Prima diagnosi": "首次诊断",
        "Crawl fino a %(n)s pagine. ": "最多抓取 %(n)s 个页面。",
        "Include probe SoV Misurato (Plus). ": (
            "包含实测 SoV 探测（Plus）。"
        ),
        "Ricalcola score e findings dopo eventuali fix pubblicati. Gli score possono salire o scendere — non è un miglioramento garantito.": (
            "在发布修复后重新计算评分与 findings。"
            "分数可能上升或下降——不保证一定会改善。"
        ),
        "Misura i segnali pubblici attuali e produce score AIO/GEO, findings e pack. Non prevede un guadagno di score: il risultato dipende dal sito.": (
            "测量当前公开信号，并生成 AIO/GEO 评分、findings 与修复包。"
            "不承诺分数提升：结果取决于网站本身。"
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
        mo_path = po_path.with_suffix(".mo")
        with mo_path.open("wb") as fh:
            write_mo(fh, cat)
        print(f"updated {po_path.relative_to(ROOT)} ({len(table)} strings)")


if __name__ == "__main__":
    main()
