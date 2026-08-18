#!/usr/bin/env python3
"""Upsert native GEO Charts chrome gettext strings and compile .mo."""

from __future__ import annotations

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]

# Shared with insights card + expanded Charts chrome (Italian msgids).
STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "Insight GEO actionable": "Actionable GEO Insights",
        "Nessun finding critico/warn nell'ultimo audit.": (
            "No critical/warn findings in the latest audit."
        ),
        "Pagine valutate": "Pages scored",
        "findings nell'ultimo audit": "findings in last audit",
        "In ordine": "Clear",
        "Da monitorare": "Watch",
        "Elevata": "Elevated",
        "Alta": "High",
        "Info": "Info",
        "Critico": "Critical",
        "Attenzione": "Warning",
        "GEO Charts": "GEO Charts",
        "Panoramica GEO": "GEO Overview",
        "Nessuna analisi ancora. Esegui un audit per vedere Share of Model, "
        "engine breakdown e insight dal tuo sito — niente dati demo.": (
            "No analysis yet. Run an audit to see Share of Model, engine "
            "breakdown, and insights from your site — no demo data."
        ),
        "Esegui audit GEO": "Run GEO audit",
        "Share of Model e visibilità AI dall'ultimo audit.": (
            "Share of Model and AI visibility from your latest audit."
        ),
        "Ultimi 30 giorni": "Last 30 days",
        "Ultimi 7 giorni": "Last 7 days",
        "Trimestre in corso": "Quarter to date",
        "Range storico: in arrivo": "Historical range: coming soon",
        "Share of Model": "Share of Model",
        "su %(n)s engine LLM tracciati": "across %(n)s tracked LLM engines",
        "Ranking AI": "AI rank",
        "Grado composito da AIO/GEO": "Composite grade from AIO/GEO",
        "Pressione findings": "Issue pressure",
        "Critical + warn aperti (non sentiment del modello)": (
            "Critical + warn open (not model sentiment)"
        ),
        "Trend Share of Model": "Share of Model trend",
        "Breakdown visibilità LLM": "LLM visibility breakdown",
        "Vedi report dettagliato": "View detailed report",
        "Nessun engine breakdown ancora — riesegui l'audit.": (
            "No engine breakdown yet — re-run the audit."
        ),
        "Engine": "Engine",
        "Share of Voice": "Share of Voice",
        "Dominio più citato": "Top cited domain",
        "Stato": "Status",
        "Dominante": "Dominant",
        "Ottimale": "Optimal",
        "Da migliorare": "Needs action",
    },
    "de": {
        "Insight GEO actionable": "Umsetzbare GEO-Insights",
        "Nessun finding critico/warn nell'ultimo audit.": (
            "Keine kritischen/Warn-Findings im letzten Audit."
        ),
        "Pagine valutate": "Bewertete Seiten",
        "findings nell'ultimo audit": "Findings im letzten Audit",
        "In ordine": "In Ordnung",
        "Da monitorare": "Beobachten",
        "Elevata": "Erhöht",
        "Alta": "Hoch",
        "Info": "Info",
        "Critico": "Kritisch",
        "Attenzione": "Warnung",
        "GEO Charts": "GEO Charts",
        "Panoramica GEO": "GEO-Übersicht",
        "Nessuna analisi ancora. Esegui un audit per vedere Share of Model, "
        "engine breakdown e insight dal tuo sito — niente dati demo.": (
            "Noch keine Analyse. Führen Sie ein Audit aus, um Share of Model, "
            "Engine-Breakdown und Insights zu Ihrer Site zu sehen — keine Demo-Daten."
        ),
        "Esegui audit GEO": "GEO-Audit starten",
        "Share of Model e visibilità AI dall'ultimo audit.": (
            "Share of Model und AI-Sichtbarkeit aus dem letzten Audit."
        ),
        "Ultimi 30 giorni": "Letzte 30 Tage",
        "Ultimi 7 giorni": "Letzte 7 Tage",
        "Trimestre in corso": "Aktuelles Quartal",
        "Range storico: in arrivo": "Historischer Zeitraum: demnächst",
        "Share of Model": "Share of Model",
        "su %(n)s engine LLM tracciati": "über %(n)s getrackte LLM-Engines",
        "Ranking AI": "AI-Rang",
        "Grado composito da AIO/GEO": "Zusammengesetzte Note aus AIO/GEO",
        "Pressione findings": "Finding-Druck",
        "Critical + warn aperti (non sentiment del modello)": (
            "Offene Critical + Warn (kein Modell-Sentiment)"
        ),
        "Trend Share of Model": "Share-of-Model-Trend",
        "Breakdown visibilità LLM": "LLM-Sichtbarkeits-Breakdown",
        "Vedi report dettagliato": "Detaillierten Report ansehen",
        "Nessun engine breakdown ancora — riesegui l'audit.": (
            "Noch kein Engine-Breakdown — Audit erneut ausführen."
        ),
        "Engine": "Engine",
        "Share of Voice": "Share of Voice",
        "Dominio più citato": "Meistzitierte Domain",
        "Stato": "Status",
        "Dominante": "Dominant",
        "Ottimale": "Optimal",
        "Da migliorare": "Handlungsbedarf",
    },
    "es": {
        "Insight GEO actionable": "Insights GEO accionables",
        "Nessun finding critico/warn nell'ultimo audit.": (
            "Sin findings críticos/aviso en la última auditoría."
        ),
        "Pagine valutate": "Páginas evaluadas",
        "findings nell'ultimo audit": "findings en la última auditoría",
        "In ordine": "En orden",
        "Da monitorare": "Vigilancia",
        "Elevata": "Elevada",
        "Alta": "Alta",
        "Info": "Info",
        "Critico": "Crítico",
        "Attenzione": "Atención",
        "GEO Charts": "GEO Charts",
        "Panoramica GEO": "Panorámica GEO",
        "Nessuna analisi ancora. Esegui un audit per vedere Share of Model, "
        "engine breakdown e insight dal tuo sito — niente dati demo.": (
            "Aún no hay análisis. Ejecuta una auditoría para ver Share of Model, "
            "desglose de engines e insights de tu sitio — sin datos demo."
        ),
        "Esegui audit GEO": "Ejecutar auditoría GEO",
        "Share of Model e visibilità AI dall'ultimo audit.": (
            "Share of Model y visibilidad AI de la última auditoría."
        ),
        "Ultimi 30 giorni": "Últimos 30 días",
        "Ultimi 7 giorni": "Últimos 7 días",
        "Trimestre in corso": "Trimestre en curso",
        "Range storico: in arrivo": "Rango histórico: próximamente",
        "Share of Model": "Share of Model",
        "su %(n)s engine LLM tracciati": "en %(n)s engines LLM rastreados",
        "Ranking AI": "Ranking AI",
        "Grado composito da AIO/GEO": "Grado compuesto de AIO/GEO",
        "Pressione findings": "Presión de findings",
        "Critical + warn aperti (non sentiment del modello)": (
            "Critical + warn abiertos (no sentimiento del modelo)"
        ),
        "Trend Share of Model": "Tendencia Share of Model",
        "Breakdown visibilità LLM": "Desglose de visibilidad LLM",
        "Vedi report dettagliato": "Ver informe detallado",
        "Nessun engine breakdown ancora — riesegui l'audit.": (
            "Aún no hay desglose de engines — vuelve a ejecutar la auditoría."
        ),
        "Engine": "Engine",
        "Share of Voice": "Share of Voice",
        "Dominio più citato": "Dominio más citado",
        "Stato": "Estado",
        "Dominante": "Dominante",
        "Ottimale": "Óptimo",
        "Da migliorare": "A mejorar",
    },
    "ko": {
        "Insight GEO actionable": "실행 가능한 GEO 인사이트",
        "Nessun finding critico/warn nell'ultimo audit.": (
            "최근 감사에 심각/주의 파인딩이 없습니다."
        ),
        "Pagine valutate": "평가된 페이지",
        "findings nell'ultimo audit": "최근 감사의 파인딩",
        "In ordine": "양호",
        "Da monitorare": "주시",
        "Elevata": "높음",
        "Alta": "매우 높음",
        "Info": "정보",
        "Critico": "심각",
        "Attenzione": "주의",
        "GEO Charts": "GEO Charts",
        "Panoramica GEO": "GEO 개요",
        "Nessuna analisi ancora. Esegui un audit per vedere Share of Model, "
        "engine breakdown e insight dal tuo sito — niente dati demo.": (
            "아직 분석이 없습니다. Share of Model, 엔진 분석, 사이트 인사이트를 "
            "보려면 감사를 실행하세요 — 데모 데이터 없음."
        ),
        "Esegui audit GEO": "GEO 감사 실행",
        "Share of Model e visibilità AI dall'ultimo audit.": (
            "최근 감사의 Share of Model 및 AI 가시성."
        ),
        "Ultimi 30 giorni": "최근 30일",
        "Ultimi 7 giorni": "최근 7일",
        "Trimestre in corso": "이번 분기",
        "Range storico: in arrivo": "기간 범위: 곧 제공",
        "Share of Model": "Share of Model",
        "su %(n)s engine LLM tracciati": "추적 중인 LLM 엔진 %(n)s개",
        "Ranking AI": "AI 순위",
        "Grado composito da AIO/GEO": "AIO/GEO 복합 등급",
        "Pressione findings": "파인딩 압력",
        "Critical + warn aperti (non sentiment del modello)": (
            "열린 심각+주의 (모델 감성 아님)"
        ),
        "Trend Share of Model": "Share of Model 추세",
        "Breakdown visibilità LLM": "LLM 가시성 분석",
        "Vedi report dettagliato": "상세 리포트 보기",
        "Nessun engine breakdown ancora — riesegui l'audit.": (
            "아직 엔진 분석이 없습니다 — 감사를 다시 실행하세요."
        ),
        "Engine": "엔진",
        "Share of Voice": "Share of Voice",
        "Dominio più citato": "최다 인용 도메인",
        "Stato": "상태",
        "Dominante": "지배적",
        "Ottimale": "최적",
        "Da migliorare": "개선 필요",
    },
    "zh_Hans": {
        "Insight GEO actionable": "可执行的 GEO 洞察",
        "Nessun finding critico/warn nell'ultimo audit.": (
            "最近一次审计中无严重/警告发现。"
        ),
        "Pagine valutate": "已评分页面",
        "findings nell'ultimo audit": "最近一次审计中的发现",
        "In ordine": "正常",
        "Da monitorare": "关注",
        "Elevata": "偏高",
        "Alta": "高",
        "Info": "信息",
        "Critico": "严重",
        "Attenzione": "警告",
        "GEO Charts": "GEO Charts",
        "Panoramica GEO": "GEO 概览",
        "Nessuna analisi ancora. Esegui un audit per vedere Share of Model, "
        "engine breakdown e insight dal tuo sito — niente dati demo.": (
            "尚无分析。运行审计即可查看 Share of Model、引擎拆解与站点洞察——"
            "无演示数据。"
        ),
        "Esegui audit GEO": "运行 GEO 审计",
        "Share of Model e visibilità AI dall'ultimo audit.": (
            "来自最近一次审计的 Share of Model 与 AI 可见性。"
        ),
        "Ultimi 30 giorni": "最近 30 天",
        "Ultimi 7 giorni": "最近 7 天",
        "Trimestre in corso": "本季度",
        "Range storico: in arrivo": "历史区间：即将推出",
        "Share of Model": "Share of Model",
        "su %(n)s engine LLM tracciati": "覆盖 %(n)s 个已跟踪 LLM 引擎",
        "Ranking AI": "AI 排名",
        "Grado composito da AIO/GEO": "来自 AIO/GEO 的综合等级",
        "Pressione findings": "发现压力",
        "Critical + warn aperti (non sentiment del modello)": (
            "未关闭的严重+警告（非模型情绪）"
        ),
        "Trend Share of Model": "Share of Model 趋势",
        "Breakdown visibilità LLM": "LLM 可见性拆解",
        "Vedi report dettagliato": "查看详细报告",
        "Nessun engine breakdown ancora — riesegui l'audit.": (
            "尚无引擎拆解 — 请重新运行审计。"
        ),
        "Engine": "引擎",
        "Share of Voice": "Share of Voice",
        "Dominio più citato": "最高引用域名",
        "Stato": "状态",
        "Dominante": "主导",
        "Ottimale": "最佳",
        "Da migliorare": "待改进",
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
    for loc, table in STRINGS.items():
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
