#!/usr/bin/env python3
"""Upsert native pack-mail dialog strings into gettext catalogs and compile .mo."""

from __future__ import annotations

from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]
LOCALES = {
    "en": ROOT / "translations/en/LC_MESSAGES/messages.po",
    "de": ROOT / "translations/de/LC_MESSAGES/messages.po",
    "es": ROOT / "translations/es/LC_MESSAGES/messages.po",
    "zh": ROOT / "translations/zh_Hans/LC_MESSAGES/messages.po",
    "ko": ROOT / "translations/ko/LC_MESSAGES/messages.po",
}

# Italian msgid → native msgstr per locale.
STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "Invia pack via email": "Send pack by email",
        "Inserisci l’indirizzo email dove vuoi ricevere il pack HTML per questo dominio.": (
            "Enter the email address where you want to receive the HTML pack for this domain."
        ),
        "Indirizzo email": "Email address",
        "Puoi inviarlo a te o a un collega. Limite giornaliero anti-abuso attivo.": (
            "You can send it to yourself or a colleague. A daily anti-abuse limit applies."
        ),
        "Invia pack": "Send pack",
        "Un unico HTML con head snippet, llms.txt, robots e checklist — pronto da applicare sul sito live.": (
            "A single HTML file with head snippet, llms.txt, robots, and checklist — ready to apply on the live site."
        ),
        "Indirizzo email non valido.": "Invalid email address.",
        "Limite raggiunto: massimo %(n)s invii pack / 24h.": (
            "Limit reached: maximum %(n)s pack sends / 24h."
        ),
        "Invio email non riuscito. Riprova tra poco o scarica il file HTML.": (
            "Email could not be sent. Try again shortly or download the HTML file."
        ),
        "Pack inviato a %(email)s.": "Pack sent to %(email)s.",
        "Invio email non ancora attivo su questo server. Puoi scaricare il file HTML intanto.": (
            "Email sending is not active on this server yet. You can download the HTML file for now."
        ),
        "Analisi non trovata.": "Analysis not found.",
    },
    "de": {
        "Invia pack via email": "Pack per E-Mail senden",
        "Inserisci l’indirizzo email dove vuoi ricevere il pack HTML per questo dominio.": (
            "Geben Sie die E-Mail-Adresse ein, an die Sie das HTML-Pack für diese Domain erhalten möchten."
        ),
        "Indirizzo email": "E-Mail-Adresse",
        "Puoi inviarlo a te o a un collega. Limite giornaliero anti-abuso attivo.": (
            "Sie können es an sich selbst oder an einen Kollegen senden. Es gilt ein tägliches Anti-Missbrauchs-Limit."
        ),
        "Invia pack": "Pack senden",
        "Un unico HTML con head snippet, llms.txt, robots e checklist — pronto da applicare sul sito live.": (
            "Eine einzelne HTML-Datei mit Head-Snippet, llms.txt, robots und Checkliste — bereit zur Anwendung auf der Live-Website."
        ),
        "Indirizzo email non valido.": "Ungültige E-Mail-Adresse.",
        "Limite raggiunto: massimo %(n)s invii pack / 24h.": (
            "Limit erreicht: maximal %(n)s Pack-Sendungen / 24 Std."
        ),
        "Invio email non riuscito. Riprova tra poco o scarica il file HTML.": (
            "E-Mail-Versand fehlgeschlagen. Bitte versuchen Sie es gleich erneut oder laden Sie die HTML-Datei herunter."
        ),
        "Pack inviato a %(email)s.": "Pack an %(email)s gesendet.",
        "Invio email non ancora attivo su questo server. Puoi scaricare il file HTML intanto.": (
            "Der E-Mail-Versand ist auf diesem Server noch nicht aktiv. Sie können die HTML-Datei vorerst herunterladen."
        ),
        "Analisi non trovata.": "Analyse nicht gefunden.",
    },
    "es": {
        "Invia pack via email": "Enviar pack por email",
        "Inserisci l’indirizzo email dove vuoi ricevere il pack HTML per questo dominio.": (
            "Introduce la dirección de email donde quieres recibir el pack HTML de este dominio."
        ),
        "Indirizzo email": "Dirección de email",
        "Puoi inviarlo a te o a un collega. Limite giornaliero anti-abuso attivo.": (
            "Puedes enviártelo a ti o a un compañero. Hay un límite diario antabuso."
        ),
        "Invia pack": "Enviar pack",
        "Un unico HTML con head snippet, llms.txt, robots e checklist — pronto da applicare sul sito live.": (
            "Un único HTML con snippet del head, llms.txt, robots y checklist — listo para aplicar en el sitio en producción."
        ),
        "Indirizzo email non valido.": "Dirección de email no válida.",
        "Limite raggiunto: massimo %(n)s invii pack / 24h.": (
            "Límite alcanzado: máximo %(n)s envíos de pack / 24 h."
        ),
        "Invio email non riuscito. Riprova tra poco o scarica il file HTML.": (
            "No se pudo enviar el email. Inténtalo en breve o descarga el archivo HTML."
        ),
        "Pack inviato a %(email)s.": "Pack enviado a %(email)s.",
        "Invio email non ancora attivo su questo server. Puoi scaricare il file HTML intanto.": (
            "El envío de email aún no está activo en este servidor. Mientras tanto puedes descargar el archivo HTML."
        ),
        "Analisi non trovata.": "Análisis no encontrado.",
    },
    "zh": {
        "Invia pack via email": "通过邮件发送优化包",
        "Inserisci l’indirizzo email dove vuoi ricevere il pack HTML per questo dominio.": (
            "请输入要接收此域名 HTML 优化包的邮箱地址。"
        ),
        "Indirizzo email": "邮箱地址",
        "Puoi inviarlo a te o a un collega. Limite giornaliero anti-abuso attivo.": (
            "可发给自己或同事。已启用每日防滥用限制。"
        ),
        "Invia pack": "发送优化包",
        "Un unico HTML con head snippet, llms.txt, robots e checklist — pronto da applicare sul sito live.": (
            "单个 HTML 文件，包含 head 片段、llms.txt、robots 与清单 — 可直接应用到线上站点。"
        ),
        "Indirizzo email non valido.": "邮箱地址无效。",
        "Limite raggiunto: massimo %(n)s invii pack / 24h.": (
            "已达上限：24 小时内最多发送 %(n)s 次优化包。"
        ),
        "Invio email non riuscito. Riprova tra poco o scarica il file HTML.": (
            "邮件发送失败。请稍后重试，或先下载 HTML 文件。"
        ),
        "Pack inviato a %(email)s.": "优化包已发送至 %(email)s。",
        "Invio email non ancora attivo su questo server. Puoi scaricare il file HTML intanto.": (
            "此服务器尚未启用邮件发送。你可先下载 HTML 文件。"
        ),
        "Analisi non trovata.": "未找到分析。",
    },
    "ko": {
        "Invia pack via email": "이메일로 팩 보내기",
        "Inserisci l’indirizzo email dove vuoi ricevere il pack HTML per questo dominio.": (
            "이 도메인의 HTML 팩을 받을 이메일 주소를 입력하세요."
        ),
        "Indirizzo email": "이메일 주소",
        "Puoi inviarlo a te o a un collega. Limite giornaliero anti-abuso attivo.": (
            "본인 또는 동료에게 보낼 수 있습니다. 일일 남용 방지 한도가 적용됩니다."
        ),
        "Invia pack": "팩 보내기",
        "Un unico HTML con head snippet, llms.txt, robots e checklist — pronto da applicare sul sito live.": (
            "head 스니펫, llms.txt, robots, 체크리스트가 담긴 단일 HTML — 라이브 사이트에 바로 적용할 수 있습니다."
        ),
        "Indirizzo email non valido.": "유효하지 않은 이메일 주소입니다.",
        "Limite raggiunto: massimo %(n)s invii pack / 24h.": (
            "한도 초과: 24시간 내 팩 발송은 최대 %(n)s회입니다."
        ),
        "Invio email non riuscito. Riprova tra poco o scarica il file HTML.": (
            "이메일 전송에 실패했습니다. 잠시 후 다시 시도하거나 HTML 파일을 다운로드하세요."
        ),
        "Pack inviato a %(email)s.": "%(email)s(으)로 팩을 보냈습니다.",
        "Invio email non ancora attivo su questo server. Puoi scaricare il file HTML intanto.": (
            "이 서버에서는 아직 이메일 발송이 활성화되지 않았습니다. 그동안 HTML 파일을 다운로드할 수 있습니다."
        ),
        "Analisi non trovata.": "분석을 찾을 수 없습니다.",
    },
}


def upsert(catalog: Catalog, msgid: str, msgstr: str) -> None:
    msg = catalog.get(msgid)
    if msg is None:
        catalog.add(msgid, msgstr, flags=[])
        return
    msg.string = msgstr
    # Clear fuzzy so compiled catalog uses the string.
    if msg.flags:
        msg.flags.discard("fuzzy")


def main() -> None:
    # Keep apostrophe identical to templates/dashboard.html (U+2019).
    lede_it = (
        "Inserisci l\u2019indirizzo email dove vuoi ricevere "
        "il pack HTML per questo dominio."
    )
    for loc, path in LOCALES.items():
        table = dict(STRINGS[loc])
        # Ensure lede key uses the template apostrophe even if source edited ASCII.
        ascii_lede = (
            "Inserisci l'indirizzo email dove vuoi ricevere "
            "il pack HTML per questo dominio."
        )
        if ascii_lede in table and lede_it not in table:
            table[lede_it] = table.pop(ascii_lede)
        with path.open("rb") as fh:
            cat = read_po(fh)
        for msgid, msgstr in table.items():
            upsert(cat, msgid, msgstr)
        with path.open("wb") as fh:
            write_po(fh, cat, ignore_obsolete=False, include_previous=False, width=80)
        mo_path = path.with_suffix(".mo")
        with mo_path.open("wb") as fh:
            write_mo(fh, cat)
        print(f"updated {path.relative_to(ROOT)} (+{len(table)} strings) → {mo_path.name}")


if __name__ == "__main__":
    main()
