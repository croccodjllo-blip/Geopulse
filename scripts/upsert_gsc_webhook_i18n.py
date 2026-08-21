#!/usr/bin/env python3
"""Upsert settings webhook + GSC connector gettext strings and compile .mo."""

from __future__ import annotations

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]

# Italian msgid → native msgstr
TABLES: dict[str, dict[str, str]] = {
    "en": {
        "Opzionale. Salvato cifrato a riposo; non viene mai rimostrato in chiaro dopo il salvataggio.": (
            "Optional. Stored encrypted at rest; never shown in plaintext after saving."
        ),
        "Secret già impostato (cifrato a riposo). Lascia vuoto per mantenerlo; scrivi “clear” per rimuoverlo.": (
            "Secret already set (encrypted at rest). Leave blank to keep it; type “clear” to remove it."
        ),
        "Pronto per il collegamento OAuth": "Ready for OAuth connection",
        "Collega Google Search Console (sola lettura) per questo account.": (
            "Connect Google Search Console (read-only) for this account."
        ),
        "Collega Google": "Connect Google",
        "Disconnetti": "Disconnect",
        "Disponibile su Plus e Business.": "Available on Plus and Business.",
        "Google Search Console": "Google Search Console",
        "Connesso": "Connected",
        "Collegato come %(email)s.": "Connected as %(email)s.",
        "Account Google collegato a Search Console (sola lettura).": (
            "Google account connected to Search Console (read-only)."
        ),
        "Proprietà visibili: %(n)s.": "Visible properties: %(n)s.",
        "Imposta GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET.": (
            "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."
        ),
        "Integrazione GSC non ancora collegabile.": (
            "GSC integration is not connectable yet."
        ),
    },
    "de": {
        "Opzionale. Salvato cifrato a riposo; non viene mai rimostrato in chiaro dopo il salvataggio.": (
            "Optional. Verschlüsselt gespeichert; nach dem Speichern nie im Klartext angezeigt."
        ),
        "Secret già impostato (cifrato a riposo). Lascia vuoto per mantenerlo; scrivi “clear” per rimuoverlo.": (
            "Secret bereits gesetzt (verschlüsselt). Leer lassen zum Behalten; „clear“ zum Entfernen."
        ),
        "Pronto per il collegamento OAuth": "Bereit für die OAuth-Verbindung",
        "Collega Google Search Console (sola lettura) per questo account.": (
            "Google Search Console (nur Lesen) für dieses Konto verbinden."
        ),
        "Collega Google": "Google verbinden",
        "Disconnetti": "Trennen",
        "Disponibile su Plus e Business.": "Verfügbar bei Plus und Business.",
        "Google Search Console": "Google Search Console",
        "Connesso": "Verbunden",
        "Collegato come %(email)s.": "Verbunden als %(email)s.",
        "Account Google collegato a Search Console (sola lettura).": (
            "Google-Konto mit Search Console verbunden (nur Lesen)."
        ),
        "Proprietà visibili: %(n)s.": "Sichtbare Properties: %(n)s.",
        "Imposta GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET.": (
            "GOOGLE_OAUTH_CLIENT_ID und GOOGLE_OAUTH_CLIENT_SECRET setzen."
        ),
        "Integrazione GSC non ancora collegabile.": (
            "GSC-Integration ist noch nicht verbindbar."
        ),
    },
    "es": {
        "Opzionale. Salvato cifrato a riposo; non viene mai rimostrato in chiaro dopo il salvataggio.": (
            "Opcional. Guardado cifrado en reposo; nunca se muestra en claro tras guardar."
        ),
        "Secret già impostato (cifrato a riposo). Lascia vuoto per mantenerlo; scrivi “clear” per rimuoverlo.": (
            "Secret ya configurado (cifrado). Déjalo vacío para mantenerlo; escribe “clear” para quitarlo."
        ),
        "Pronto per il collegamento OAuth": "Listo para la conexión OAuth",
        "Collega Google Search Console (sola lettura) per questo account.": (
            "Conecta Google Search Console (solo lectura) para esta cuenta."
        ),
        "Collega Google": "Conectar Google",
        "Disconnetti": "Desconectar",
        "Disponibile su Plus e Business.": "Disponible en Plus y Business.",
        "Google Search Console": "Google Search Console",
        "Connesso": "Conectado",
        "Collegato come %(email)s.": "Conectado como %(email)s.",
        "Account Google collegato a Search Console (sola lettura).": (
            "Cuenta de Google conectada a Search Console (solo lectura)."
        ),
        "Proprietà visibili: %(n)s.": "Propiedades visibles: %(n)s.",
        "Imposta GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET.": (
            "Configura GOOGLE_OAUTH_CLIENT_ID y GOOGLE_OAUTH_CLIENT_SECRET."
        ),
        "Integrazione GSC non ancora collegabile.": (
            "La integración GSC aún no se puede conectar."
        ),
    },
    "ko": {
        "Opzionale. Salvato cifrato a riposo; non viene mai rimostrato in chiaro dopo il salvataggio.": (
            "선택 사항. 저장 시 암호화되며, 저장 후 평문으로 다시 표시되지 않습니다."
        ),
        "Secret già impostato (cifrato a riposo). Lascia vuoto per mantenerlo; scrivi “clear” per rimuoverlo.": (
            "시크릿이 이미 설정되어 있습니다(암호화). 유지하려면 비워 두고, 제거하려면 “clear”를 입력하세요."
        ),
        "Pronto per il collegamento OAuth": "OAuth 연결 준비됨",
        "Collega Google Search Console (sola lettura) per questo account.": (
            "이 계정에 Google Search Console(읽기 전용)을 연결하세요."
        ),
        "Collega Google": "Google 연결",
        "Disconnetti": "연결 해제",
        "Disponibile su Plus e Business.": "Plus 및 Business에서 사용 가능.",
        "Google Search Console": "Google Search Console",
        "Connesso": "연결됨",
        "Collegato come %(email)s.": "%(email)s(으)로 연결됨.",
        "Account Google collegato a Search Console (sola lettura).": (
            "Google 계정이 Search Console에 연결됨(읽기 전용)."
        ),
        "Proprietà visibili: %(n)s.": "표시된 속성: %(n)s개.",
        "Imposta GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET.": (
            "GOOGLE_OAUTH_CLIENT_ID 및 GOOGLE_OAUTH_CLIENT_SECRET을 설정하세요."
        ),
        "Integrazione GSC non ancora collegabile.": (
            "GSC 연동을 아직 연결할 수 없습니다."
        ),
    },
    "zh_Hans": {
        "Opzionale. Salvato cifrato a riposo; non viene mai rimostrato in chiaro dopo il salvataggio.": (
            "可选。静态加密存储；保存后不会再以明文显示。"
        ),
        "Secret già impostato (cifrato a riposo). Lascia vuoto per mantenerlo; scrivi “clear” per rimuoverlo.": (
            "密钥已设置（静态加密）。留空以保留；输入 “clear” 以删除。"
        ),
        "Pronto per il collegamento OAuth": "可进行 OAuth 连接",
        "Collega Google Search Console (sola lettura) per questo account.": (
            "为此账户连接 Google Search Console（只读）。"
        ),
        "Collega Google": "连接 Google",
        "Disconnetti": "断开连接",
        "Disponibile su Plus e Business.": "适用于 Plus 和 Business。",
        "Google Search Console": "Google Search Console",
        "Connesso": "已连接",
        "Collegato come %(email)s.": "已以 %(email)s 连接。",
        "Account Google collegato a Search Console (sola lettura).": (
            "Google 账户已连接到 Search Console（只读）。"
        ),
        "Proprietà visibili: %(n)s.": "可见媒体资源：%(n)s。",
        "Imposta GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET.": (
            "请设置 GOOGLE_OAUTH_CLIENT_ID 和 GOOGLE_OAUTH_CLIENT_SECRET。"
        ),
        "Integrazione GSC non ancora collegabile.": (
            "GSC 集成尚不可连接。"
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
