#!/usr/bin/env python3
"""Upsert native hero / preview-URL gettext strings and compile .mo catalogs."""

from __future__ import annotations

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]

# Italian msgids (source) → native msgstr per locale (babel folder name).
TABLES: dict[str, dict[str, str]] = {
    "en": {
        "Scopri quanto il tuo sito è pronto per essere compreso, citato e raccomandato dalle intelligenze artificiali.": (
            "See how ready your site is to be understood, cited, and recommended by AI."
        ),
        "Inserisci il dominio per score AIO/GEO di predisposizione strutturale e criticità.": (
            "Enter your domain for AIO/GEO structural readiness scores and critical issues."
        ),
        "Misura la": "Measure",
        "del tuo sito": "of your site",
        "per le IA": "for AI",
        "Misura la readiness": "Measure readiness",
        "del tuo sito per le IA": "of your site for AI",
        "Anteprima immediata · niente carta": "Instant preview · no credit card",
        "tuodominio.it": "yourdomain.com",
        "Analizza gratis": "Analyze free",
        "Inserisci l’URL del tuo sito (es. tuodominio.it).": (
            "Enter your site URL (e.g. yourdomain.com)."
        ),
        "URL non valido": "Invalid URL",
        "URL non valido.": "Invalid URL.",
        "Sei già collegato: avvia l’analisi dal dashboard.": (
            "You’re already signed in — start the analysis from the dashboard."
        ),
        "Troppe anteprime da questo IP. Riprova tra poco o crea un account.": (
            "Too many previews from this IP. Try again shortly or create an account."
        ),
        "Limite giornaliero anteprime raggiunto. Crea un account Free per continuare.": (
            "Daily preview limit reached. Create a Free account to continue."
        ),
        "Anteprima scaduta. Inserisci di nuovo l’URL in homepage.": (
            "Preview expired. Enter the URL again on the homepage."
        ),
        "Host mancante": "Missing host",
        "URL vuoto": "Empty URL",
        "Solo http/https consentiti": "Only http/https URLs are allowed",
        "Credenziali nell’URL non consentite": "Credentials in the URL are not allowed",
        "URL non consentito": "URL not allowed",
        "Host non risolvibile. Controlla il dominio e riprova.": (
            "Host could not be resolved. Check the domain and try again."
        ),
        "URL non consentito per l’anteprima.": "URL not allowed for preview.",
    },
    "de": {
        "Scopri quanto il tuo sito è pronto per essere compreso, citato e raccomandato dalle intelligenze artificiali.": (
            "Sehen Sie, wie bereit Ihre Website ist, von KI verstanden, zitiert und empfohlen zu werden."
        ),
        "Inserisci il dominio per score AIO/GEO di predisposizione strutturale e criticità.": (
            "Geben Sie Ihre Domain ein — für AIO/GEO-Scores zur strukturellen Bereitschaft und kritische Befunde."
        ),
        "Misura la": "Miss",
        "del tuo sito": "Ihrer Website",
        "per le IA": "für KI",
        "Misura la readiness": "Miss die Bereitschaft",
        "del tuo sito per le IA": "Ihrer Website für KI",
        "Anteprima immediata · niente carta": "Sofortvorschau · ohne Kreditkarte",
        "tuodominio.it": "deine-domain.de",
        "Analizza gratis": "Kostenlos analysieren",
        "Inserisci l’URL del tuo sito (es. tuodominio.it).": (
            "Geben Sie die URL Ihrer Website ein (z. B. deine-domain.de)."
        ),
        "URL non valido": "Ungültige URL",
        "URL non valido.": "Ungültige URL.",
        "Sei già collegato: avvia l’analisi dal dashboard.": (
            "Sie sind bereits angemeldet — starten Sie die Analyse im Dashboard."
        ),
        "Troppe anteprime da questo IP. Riprova tra poco o crea un account.": (
            "Zu viele Vorschauen von dieser IP. Bitte später erneut versuchen oder ein Konto erstellen."
        ),
        "Limite giornaliero anteprime raggiunto. Crea un account Free per continuare.": (
            "Tägliches Vorschau-Limit erreicht. Erstellen Sie ein Free-Konto, um fortzufahren."
        ),
        "Anteprima scaduta. Inserisci di nuovo l’URL in homepage.": (
            "Vorschau abgelaufen. Geben Sie die URL erneut auf der Startseite ein."
        ),
        "Host mancante": "Host fehlt",
        "URL vuoto": "Leere URL",
        "Solo http/https consentiti": "Nur http/https-URLs sind erlaubt",
        "Credenziali nell’URL non consentite": "Zugangsdaten in der URL sind nicht erlaubt",
        "URL non consentito": "URL nicht erlaubt",
        "Host non risolvibile. Controlla il dominio e riprova.": (
            "Host nicht auflösbar. Prüfen Sie die Domain und versuchen Sie es erneut."
        ),
        "URL non consentito per l’anteprima.": "URL für die Vorschau nicht erlaubt.",
    },
    "es": {
        "Scopri quanto il tuo sito è pronto per essere compreso, citato e raccomandato dalle intelligenze artificiali.": (
            "Descubre cuán listo está tu sitio para ser comprendido, citado y recomendado por la IA."
        ),
        "Inserisci il dominio per score AIO/GEO di predisposizione strutturale e criticità.": (
            "Introduce tu dominio para obtener puntuaciones AIO/GEO de preparación estructural y criticidades."
        ),
        "Misura la": "Mide",
        "del tuo sito": "de tu sitio",
        "per le IA": "para la IA",
        "Misura la readiness": "Mide la preparación",
        "del tuo sito per le IA": "de tu sitio para la IA",
        "Anteprima immediata · niente carta": "Vista previa al instante · sin tarjeta",
        "tuodominio.it": "tudominio.es",
        "Analizza gratis": "Analizar gratis",
        "Inserisci l’URL del tuo sito (es. tuodominio.it).": (
            "Introduce la URL de tu sitio (p. ej. tudominio.es)."
        ),
        "URL non valido": "URL no válida",
        "URL non valido.": "URL no válida.",
        "Sei già collegato: avvia l’analisi dal dashboard.": (
            "Ya has iniciado sesión: lanza el análisis desde el panel."
        ),
        "Troppe anteprime da questo IP. Riprova tra poco o crea un account.": (
            "Demasiadas vistas previas desde esta IP. Inténtalo más tarde o crea una cuenta."
        ),
        "Limite giornaliero anteprime raggiunto. Crea un account Free per continuare.": (
            "Has alcanzado el límite diario de vistas previas. Crea una cuenta Free para continuar."
        ),
        "Anteprima scaduta. Inserisci di nuovo l’URL in homepage.": (
            "La vista previa ha caducado. Vuelve a introducir la URL en la página de inicio."
        ),
        "Host mancante": "Falta el host",
        "URL vuoto": "URL vacía",
        "Solo http/https consentiti": "Solo se permiten URL http/https",
        "Credenziali nell’URL non consentite": "No se permiten credenciales en la URL",
        "URL non consentito": "URL no permitida",
        "Host non risolvibile. Controlla il dominio e riprova.": (
            "No se pudo resolver el host. Comprueba el dominio e inténtalo de nuevo."
        ),
        "URL non consentito per l’anteprima.": "URL no permitida para la vista previa.",
    },
    "ko": {
        "Scopri quanto il tuo sito è pronto per essere compreso, citato e raccomandato dalle intelligenze artificiali.": (
            "사이트가 AI에 이해·인용·추천될 준비가 얼마나 되었는지 확인하세요."
        ),
        "Inserisci il dominio per score AIO/GEO di predisposizione strutturale e criticità.": (
            "도메인을 입력하면 AIO/GEO 구조적 준비도 점수와 핵심 이슈를 확인할 수 있습니다."
        ),
        "Misura la": "측정하세요",
        "del tuo sito": "사이트",
        "per le IA": "AI용",
        "Misura la readiness": "준비도를 측정하세요",
        "del tuo sito per le IA": "AI가 읽는 당신의 사이트",
        "Anteprima immediata · niente carta": "즉시 미리보기 · 신용카드 불필요",
        "tuodominio.it": "yourdomain.com",
        "Analizza gratis": "무료로 분석",
        "Inserisci l’URL del tuo sito (es. tuodominio.it).": (
            "사이트 URL을 입력하세요 (예: yourdomain.com)."
        ),
        "URL non valido": "유효하지 않은 URL입니다",
        "URL non valido.": "유효하지 않은 URL입니다.",
        "Sei già collegato: avvia l’analisi dal dashboard.": (
            "이미 로그인되어 있습니다. 대시보드에서 분석을 시작하세요."
        ),
        "Troppe anteprime da questo IP. Riprova tra poco o crea un account.": (
            "이 IP에서 미리보기가 너무 많습니다. 잠시 후 다시 시도하거나 계정을 만드세요."
        ),
        "Limite giornaliero anteprime raggiunto. Crea un account Free per continuare.": (
            "일일 미리보기 한도에 도달했습니다. 계속하려면 Free 계정을 만드세요."
        ),
        "Anteprima scaduta. Inserisci di nuovo l’URL in homepage.": (
            "미리보기가 만료되었습니다. 홈페이지에서 URL을 다시 입력하세요."
        ),
        "Host mancante": "호스트가 없습니다",
        "URL vuoto": "URL이 비어 있습니다",
        "Solo http/https consentiti": "http/https URL만 허용됩니다",
        "Credenziali nell’URL non consentite": "URL에 자격 증명을 넣을 수 없습니다",
        "URL non consentito": "허용되지 않는 URL입니다",
        "Host non risolvibile. Controlla il dominio e riprova.": (
            "호스트를 확인할 수 없습니다. 도메인을 확인한 뒤 다시 시도하세요."
        ),
        "URL non consentito per l’anteprima.": "미리보기에 허용되지 않는 URL입니다.",
    },
    "zh_Hans": {
        "Scopri quanto il tuo sito è pronto per essere compreso, citato e raccomandato dalle intelligenze artificiali.": (
            "了解你的网站被 AI 理解、引用和推荐的就绪程度。"
        ),
        "Inserisci il dominio per score AIO/GEO di predisposizione strutturale e criticità.": (
            "输入域名，即可查看 AIO/GEO 结构就绪度评分与关键问题。"
        ),
        "Misura la": "衡量",
        "del tuo sito": "你的网站",
        "per le IA": "面向 AI",
        "Misura la readiness": "衡量就绪度",
        "del tuo sito per le IA": "让你的网站面向 AI",
        "Anteprima immediata · niente carta": "即时预览 · 无需银行卡",
        "tuodominio.it": "yourdomain.com",
        "Analizza gratis": "免费分析",
        "Inserisci l’URL del tuo sito (es. tuodominio.it).": (
            "请输入网站 URL（例如 yourdomain.com）。"
        ),
        "URL non valido": "无效的 URL",
        "URL non valido.": "无效的 URL。",
        "Sei già collegato: avvia l’analisi dal dashboard.": (
            "你已登录：请从控制台开始分析。"
        ),
        "Troppe anteprime da questo IP. Riprova tra poco o crea un account.": (
            "来自此 IP 的预览次数过多。请稍后再试或创建账户。"
        ),
        "Limite giornaliero anteprime raggiunto. Crea un account Free per continuare.": (
            "已达每日预览上限。请创建 Free 账户以继续。"
        ),
        "Anteprima scaduta. Inserisci di nuovo l’URL in homepage.": (
            "预览已过期。请在首页重新输入 URL。"
        ),
        "Host mancante": "缺少主机名",
        "URL vuoto": "URL 为空",
        "Solo http/https consentiti": "仅允许 http/https URL",
        "Credenziali nell’URL non consentite": "URL 中不允许包含凭据",
        "URL non consentito": "不允许的 URL",
        "Host non risolvibile. Controlla il dominio e riprova.": (
            "无法解析主机名。请检查域名后重试。"
        ),
        "URL non consentito per l’anteprima.": "该 URL 不允许用于预览。",
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
        print(f"updated {po_path.relative_to(ROOT)} ({len(table)} strings) → {mo_path.name}")


if __name__ == "__main__":
    main()
