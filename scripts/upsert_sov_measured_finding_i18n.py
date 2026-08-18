#!/usr/bin/env python3
"""Upsert native SoV-measured finding + severity label gettext strings."""

from __future__ import annotations

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]

TITLE = "SoV measured basso"
DETAIL = (
    "Poche menzioni brand nei prompt probe. Rafforza entity, llms.txt e "
    "contenuti citabili; amplia il prompt bank."
)

# Also cover the adjacent measured probe summary (static shape; numbers vary —
# title carries meaning; keep a stable template for the common case is N/A,
# so we only ship the warn finding strings + severity chrome).

TABLES: dict[str, dict[str, str]] = {
    "en": {
        TITLE: "Low Measured SoV",
        DETAIL: (
            "Few brand mentions across the probe prompts. Strengthen entity "
            "signals, llms.txt, and citable content; expand your prompt bank."
        ),
        "Critico": "Critical",
        "Attenzione": "Warning",
        "critical": "critical",
        "warn": "warn",
        "Citation monitor non configurato": "Citation monitor not configured",
        "Imposta OPENAI_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, XAI_API_KEY e/o AZURE_AI_PROJECT_ENDPOINT per SoV measured.": (
            "Set OPENAI_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, "
            "GEMINI_API_KEY, XAI_API_KEY and/or AZURE_AI_PROJECT_ENDPOINT "
            "for Measured SoV."
        ),
    },
    "de": {
        TITLE: "Niedriger Measured SoV",
        DETAIL: (
            "Wenige Markenerwähnungen in den Probe-Prompts. Stärken Sie "
            "Entity-Signale, llms.txt und zitierfähige Inhalte; erweitern Sie "
            "die Prompt-Bank."
        ),
        "Critico": "Kritisch",
        "Attenzione": "Warnung",
        "critical": "kritisch",
        "warn": "Warnung",
        "Citation monitor non configurato": "Citation Monitor nicht konfiguriert",
        "Imposta OPENAI_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, XAI_API_KEY e/o AZURE_AI_PROJECT_ENDPOINT per SoV measured.": (
            "Setzen Sie OPENAI_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, "
            "GEMINI_API_KEY, XAI_API_KEY und/oder AZURE_AI_PROJECT_ENDPOINT "
            "für Measured SoV."
        ),
    },
    "es": {
        TITLE: "SoV medido bajo",
        DETAIL: (
            "Pocas menciones de marca en los prompts de sondeo. Refuerza la "
            "entidad, llms.txt y el contenido citable; amplía el banco de prompts."
        ),
        "Critico": "Crítico",
        "Attenzione": "Atención",
        "critical": "crítico",
        "warn": "aviso",
        "Citation monitor non configurato": "Monitor de citas no configurado",
        "Imposta OPENAI_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, XAI_API_KEY e/o AZURE_AI_PROJECT_ENDPOINT per SoV measured.": (
            "Configura OPENAI_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, "
            "GEMINI_API_KEY, XAI_API_KEY y/o AZURE_AI_PROJECT_ENDPOINT "
            "para el SoV medido."
        ),
    },
    "ko": {
        TITLE: "측정 SoV 낮음",
        DETAIL: (
            "프로브 프롬프트에서 브랜드 언급이 적습니다. 엔티티 신호, llms.txt, "
            "인용 가능한 콘텐츠를 강화하고 프롬프트 뱅크를 확장하세요."
        ),
        "Critico": "심각",
        "Attenzione": "주의",
        "critical": "심각",
        "warn": "주의",
        "Citation monitor non configurato": "인용 모니터가 구성되지 않음",
        "Imposta OPENAI_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, XAI_API_KEY e/o AZURE_AI_PROJECT_ENDPOINT per SoV measured.": (
            "Measured SoV를 사용하려면 OPENAI_API_KEY, PERPLEXITY_API_KEY, "
            "ANTHROPIC_API_KEY, GEMINI_API_KEY, XAI_API_KEY 및/또는 "
            "AZURE_AI_PROJECT_ENDPOINT를 설정하세요."
        ),
    },
    "zh_Hans": {
        TITLE: "实测 SoV 偏低",
        DETAIL: (
            "探测提示词中的品牌提及很少。请加强实体信号、llms.txt 与可引用内容，并扩充提示词库。"
        ),
        "Critico": "严重",
        "Attenzione": "警告",
        "critical": "严重",
        "warn": "警告",
        "Citation monitor non configurato": "未配置引用监测",
        "Imposta OPENAI_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, XAI_API_KEY e/o AZURE_AI_PROJECT_ENDPOINT per SoV measured.": (
            "请配置 OPENAI_API_KEY、PERPLEXITY_API_KEY、ANTHROPIC_API_KEY、"
            "GEMINI_API_KEY、XAI_API_KEY 和/或 AZURE_AI_PROJECT_ENDPOINT "
            "以启用实测 SoV。"
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
