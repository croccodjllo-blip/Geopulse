#!/usr/bin/env python3
"""Fill empty/fuzzy gettext entries via MyMemory (no OpenAI key required).

Usage:
  python scripts/fill_i18n_mymemory.py
  python scripts/fill_i18n_mymemory.py --locale en
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]

LOCALES = {
    "en": ("en", "en-GB"),
    "de": ("de", "de-DE"),
    "es": ("es", "es-ES"),
    "zh": ("zh_Hans", "zh-CN"),
    "ko": ("ko", "ko-KR"),
}

# High-quality overrides for product UI (MyMemory often mangles SaaS jargon).
OVERRIDES: dict[str, dict[str, str]] = {
    "en": {
        "Quasi fatto": "Almost done",
        "Circa %(lo)s–%(hi)s s": "About %(lo)s–%(hi)s s",
        "Circa 1 minuto": "About 1 minute",
        "Circa %(minutes)s minuti": "About %(minutes)s minutes",
        "Diversi minuti (sito grande o SoV measured)": (
            "Several minutes (large site or measured SoV)"
        ),
        "In coda · stima totale ~%(eta)s": "Queued · total estimate ~%(eta)s",
        "Crawl %(done)s/%(total)s · %(eta)s rimanenti": (
            "Crawl %(done)s/%(total)s · %(eta)s remaining"
        ),
        "SoV measured sugli engine · %(eta)s": "Measured SoV across engines · %(eta)s",
        "Scoring · %(eta)s": "Scoring · %(eta)s",
        "Pack artifact · %(eta)s": "Pack artifact · %(eta)s",
        "Stima:": "Estimate:",
        "Stimato": "Estimated",
        "Misurato": "Measured",
        "Stimato (proxy)": "Estimated (proxy)",
        "Stimato — probe 0 menzioni": "Estimated — probe 0 mentions",
        "Misto (proxy + measured)": "Mixed (proxy + measured)",
        "Misto — brand SoV da proxy": "Mixed — brand SoV from proxy",
        "Ultimo errore": "Last error",
        "Analisi in corso": "Analysis in progress",
        "Analisi interrotta": "Analysis interrupted",
        "Analisi non riuscita.": "Analysis failed.",
        "Analisi non riuscita": "Analysis failed",
        "Completato": "Completed",
        "Completamento pack…": "Finishing pack…",
        "completato": "complete",
        "Errore durante l’analisi": "Error during analysis",
        "Findings critici": "Critical findings",
        "Centropic Visibility Index": "Centropic Visibility Index",
    },
    "de": {
        "Quasi fatto": "Gleich fertig",
        "Circa %(lo)s–%(hi)s s": "Etwa %(lo)s–%(hi)s s",
        "Circa 1 minuto": "Etwa 1 Minute",
        "Circa %(minutes)s minuti": "Etwa %(minutes)s Minuten",
        "Diversi minuti (sito grande o SoV measured)": (
            "Mehrere Minuten (große Site oder measured SoV)"
        ),
        "In coda · stima totale ~%(eta)s": "In Warteschlange · Gesamtschätzung ~%(eta)s",
        "Crawl %(done)s/%(total)s · %(eta)s rimanenti": (
            "Crawl %(done)s/%(total)s · %(eta)s verbleibend"
        ),
        "SoV measured sugli engine · %(eta)s": "Measured SoV über Engines · %(eta)s",
        "Scoring · %(eta)s": "Scoring · %(eta)s",
        "Pack artifact · %(eta)s": "Pack-Artefakt · %(eta)s",
        "Stima:": "Schätzung:",
        "Stimato": "Geschätzt",
        "Misurato": "Gemessen",
        "Stimato (proxy)": "Geschätzt (Proxy)",
        "Ultimo errore": "Letzter Fehler",
        "Analisi in corso": "Analyse läuft",
        "Analisi interrotta": "Analyse unterbrochen",
        "Analisi non riuscita.": "Analyse fehlgeschlagen.",
        "Completato": "Abgeschlossen",
        "completato": "abgeschlossen",
    },
    "es": {
        "Quasi fatto": "Casi listo",
        "Circa %(lo)s–%(hi)s s": "Unos %(lo)s–%(hi)s s",
        "Circa 1 minuto": "About 1 minuto",
        "Circa %(minutes)s minuti": "Unos %(minutes)s minutos",
        "Diversi minuti (sito grande o SoV measured)": (
            "Varios minutos (sitio grande o SoV measured)"
        ),
        "In coda · stima totale ~%(eta)s": "En cola · estimación total ~%(eta)s",
        "Crawl %(done)s/%(total)s · %(eta)s rimanenti": (
            "Crawl %(done)s/%(total)s · %(eta)s restantes"
        ),
        "SoV measured sugli engine · %(eta)s": "SoV measured en engines · %(eta)s",
        "Scoring · %(eta)s": "Scoring · %(eta)s",
        "Pack artifact · %(eta)s": "Pack artifact · %(eta)s",
        "Stima:": "Estimación:",
        "Stimato": "Estimado",
        "Misurato": "Medido",
        "Stimato (proxy)": "Estimado (proxy)",
        "Ultimo errore": "Último error",
        "Analisi in corso": "Análisis en curso",
        "Analisi interrotta": "Análisis interrumpido",
        "Analisi non riuscita.": "Análisis fallido.",
        "Completato": "Completado",
        "completato": "completado",
    },
    "zh": {
        "Quasi fatto": "即将完成",
        "Circa %(lo)s–%(hi)s s": "约 %(lo)s–%(hi)s 秒",
        "Circa 1 minuto": "约 1 分钟",
        "Circa %(minutes)s minuti": "约 %(minutes)s 分钟",
        "Diversi minuti (sito grande o SoV measured)": (
            "数分钟（大型站点或 measured SoV）"
        ),
        "In coda · stima totale ~%(eta)s": "排队中 · 总预计 ~%(eta)s",
        "Crawl %(done)s/%(total)s · %(eta)s rimanenti": (
            "抓取 %(done)s/%(total)s · 剩余 %(eta)s"
        ),
        "SoV measured sugli engine · %(eta)s": "各引擎 measured SoV · %(eta)s",
        "Scoring · %(eta)s": "评分中 · %(eta)s",
        "Pack artifact · %(eta)s": "打包产物 · %(eta)s",
        "Stima:": "预计：",
        "Stimato": "估算",
        "Misurato": "实测",
        "Stimato (proxy)": "估算（proxy）",
        "Ultimo errore": "上次错误",
        "Analisi in corso": "分析进行中",
        "Analisi interrotta": "分析已中断",
        "Analisi non riuscita.": "分析失败。",
        "Completato": "已完成",
        "completato": "已完成",
    },
    "ko": {
        "Quasi fatto": "거의 완료",
        "Circa %(lo)s–%(hi)s s": "약 %(lo)s–%(hi)s초",
        "Circa 1 minuto": "약 1분",
        "Circa %(minutes)s minuti": "약 %(minutes)s분",
        "Diversi minuti (sito grande o SoV measured)": (
            "수 분 소요(대형 사이트 또는 measured SoV)"
        ),
        "In coda · stima totale ~%(eta)s": "대기 중 · 총 예상 ~%(eta)s",
        "Crawl %(done)s/%(total)s · %(eta)s rimanenti": (
            "크롤 %(done)s/%(total)s · 남은 시간 %(eta)s"
        ),
        "SoV measured sugli engine · %(eta)s": "엔진별 measured SoV · %(eta)s",
        "Scoring · %(eta)s": "채점 중 · %(eta)s",
        "Pack artifact · %(eta)s": "팩 아티팩트 · %(eta)s",
        "Stima:": "예상:",
        "Stimato": "추정",
        "Misurato": "측정",
        "Stimato (proxy)": "추정(proxy)",
        "Ultimo errore": "마지막 오류",
        "Analisi in corso": "분석 진행 중",
        "Analisi interrotta": "분석 중단됨",
        "Analisi non riuscita.": "분석 실패.",
        "Completato": "완료",
        "completato": "완료",
    },
}

PROTECT = (
    "Centropic",
    "AIO",
    "GEO",
    "CVI",
    "SoV",
    "llms.txt",
    "ai.txt",
    "JSON-LD",
    "Schema.org",
    "FAQPage",
    "Organization",
    "LocalBusiness",
    "WebSite",
    "ChatGPT",
    "Claude",
    "Perplexity",
    "GPTBot",
    "ClaudeBot",
    "PerplexityBot",
    "Google-Extended",
    "Open Graph",
    "Plus",
    "HTTPS",
    "HTTP",
    "DNS",
    "SSL",
    "TLS",
    "CDN",
    "WAF",
    "NAP",
    "E-E-A-T",
    "hreflang",
)


def mymemory_translate(text: str, target: str) -> str | None:
    q = urllib.parse.urlencode({"q": text, "langpair": f"it|{target}"})
    url = f"https://api.mymemory.translated.net/get?{q}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"  mymemory error: {exc}")
        return None
    if data.get("responseStatus") != 200:
        return None
    out = (data.get("responseData") or {}).get("translatedText")
    if not isinstance(out, str) or not out.strip():
        return None
    # MyMemory sometimes echoes INVALID QUERY / MYMEMORY WARNING
    if "MYMEMORY WARNING" in out.upper() or out.upper().startswith("INVALID"):
        return None
    return out.strip()


def compile_all() -> None:
    import subprocess
    import sys

    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "babel.messages.frontend",
            "compile",
            "-d",
            "translations",
            "--statistics",
        ],
        cwd=ROOT,
    )


def fill_one(short: str, babel_loc: str) -> int:
    po_path = ROOT / "translations" / babel_loc / "LC_MESSAGES" / "messages.po"
    with po_path.open("r", encoding="utf-8") as fh:
        catalog: Catalog = read_po(fh)
    overrides = OVERRIDES.get(short, {})
    # MyMemory language code (zh-CN etc. → zh)
    mm_lang = {"en": "en", "de": "de", "es": "es", "zh": "zh-CN", "ko": "ko"}[short]
    updated = 0
    for msg in catalog:
        if not msg.id or msg.id == "" or isinstance(msg.id, tuple):
            continue
        src = str(msg.id)
        empty = not (msg.string or "").strip()
        if not empty and not msg.fuzzy:
            continue
        # Skip bogus short keys that slipped into pot historically
        if src in {"title", "message", "hint"} and len(src) < 8:
            msg.string = src
            if msg.fuzzy and "fuzzy" in msg.flags:
                msg.flags.discard("fuzzy")
            updated += 1
            continue
        translated = overrides.get(src)
        if not translated:
            translated = mymemory_translate(src, mm_lang)
            time.sleep(0.35)
        if not translated:
            print(f"  skip: {src[:60]!r}")
            continue
        # Preserve placeholders
        for ph in ("%(lo)s", "%(hi)s", "%(minutes)s", "%(eta)s", "%(done)s", "%(total)s"):
            if ph in src and ph not in translated:
                # keep Italian source if placeholder lost
                print(f"  placeholder lost for {src!r} → {translated!r}")
                translated = None
                break
        if not translated:
            continue
        msg.string = translated
        if msg.fuzzy and "fuzzy" in msg.flags:
            msg.flags.discard("fuzzy")
        updated += 1
        if updated % 25 == 0:
            print(f"  [{short}] {updated} filled…")
    with po_path.open("wb") as fh:
        write_po(fh, catalog, ignore_obsolete=True)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locale", choices=sorted(LOCALES), default=None)
    args = parser.parse_args()
    targets = (
        {args.locale: LOCALES[args.locale]} if args.locale else LOCALES
    )
    total = 0
    for short, (babel_loc, _) in targets.items():
        print(f"== {short}/{babel_loc} ==")
        total += fill_one(short, babel_loc)
    compile_all()
    print(f"Done. Updated {total} entries.")


if __name__ == "__main__":
    main()
