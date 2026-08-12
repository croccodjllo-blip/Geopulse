#!/usr/bin/env python3
"""Apply native-speaker translation pass to Centropic gettext catalogs."""

from __future__ import annotations

import json
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]
WORK = Path("/tmp/i18n_work")

# Extra UI polish beyond empty/critical dumps (force overwrite + unfuzzy).
EXTRA: dict[str, dict[str, str]] = {
    "en": {
        "Sales only": "Sales only",
        "Waitlist": "Waitlist",
        "In vendita": "Available now",
        "Vedi Plus": "See Plus",
        "Waitlist Business": "Business waitlist",
        "Evidence:": "Evidence:",
        "LIVE": "LIVE",
        "Prefisso internazionale": "Country code",
        "Entra in dashboard, analizza il dominio e scarica il pack.": (
            "Sign in to the dashboard, analyze your domain, and download the pack."
        ),
        "Quote Free esaurite · passa a Plus per continuare": (
            "Free quota used up · upgrade to Plus to continue"
        ),
        "Esci": "Log out",
        "Contatti": "Contact",
        "Chi siamo": "About",
        "Guida": "Guide",
        "Storico": "History",
        "Impostazioni": "Settings",
        "Dashboard": "Dashboard",
        "Prezzi": "Pricing",
        "Prodotto": "Product",
        "FAQ": "FAQ",
        "Inizia gratis": "Start free",
        "Confronta i piani": "Compare plans",
        "Passa a Plus": "Upgrade to Plus",
        "Crea account": "Create account",
        "Bentornato": "Welcome back",
        "Password dimenticata?": "Forgot password?",
        "Chiudi": "Close",
        "Mostra": "Show",
        "Nascondi": "Hide",
        "Accedi": "Sign in",
        "Registrati": "Sign up",
        "Accesso": "Sign in",
        "Nome e cognome": "Full name",
        "Hai già un account?": "Already have an account?",
        "Nuovo su Centropic?": "New to Centropic?",
        "Accetto i": "I accept the",
        "Termini": "Terms",
        "Informativa privacy": "Privacy Policy",
        "Reinvia email di conferma": "Resend confirmation email",
        "Resta connesso su questo dispositivo (30 giorni)": (
            "Stay signed in on this device (30 days)"
        ),
        "Principale": "Main",
        "Amplia copertura": "Add coverage",
        "Copertura del piano": "Plan coverage",
        "Copertura stimata": "Estimated coverage",
        "Copertura insufficiente": "Insufficient coverage",
        "Copertura extra": "Extra coverage",
        "Copertura residua": "Remaining coverage",
        "Amplia la copertura del mese": "Add coverage for this month",
        "Il": "The",
        "Elenco prompt usati per SoV measured; personalizzabile in Impostazioni.": (
            "Prompt list used for measured SoV; customizable in Settings."
        ),
        "Analizza il tuo dominio": "Analyze your domain",
        "URL del sito": "Website URL",
        "Vedi un report di esempio": "See a sample report",
        "Anteprima immediata · niente carta": "Instant preview · no card required",
        "In vendita": "Available now",
    },
    "de": {
        "Sales only": "Nur über Sales",
        "Waitlist": "Warteliste",
        "In vendita": "Jetzt verfügbar",
        "Vedi Plus": "Plus ansehen",
        "Waitlist Business": "Business-Warteliste",
        "Evidence:": "Evidence:",
        "LIVE": "LIVE",
        "Prefisso internazionale": "Ländervorwahl",
        "Entra in dashboard, analizza il dominio e scarica il pack.": (
            "Melden Sie sich im Dashboard an, analysieren Sie Ihre Domain und laden Sie das Pack herunter."
        ),
        "Quote Free esaurite · passa a Plus per continuare": (
            "Free-Kontingent aufgebraucht · auf Plus upgraden, um fortzufahren"
        ),
        "Esci": "Abmelden",
        "Contatti": "Kontakt",
        "Chi siamo": "Über uns",
        "Guida": "Leitfaden",
        "Storico": "Verlauf",
        "Impostazioni": "Einstellungen",
        "Dashboard": "Dashboard",
        "Prezzi": "Preise",
        "Prodotto": "Produkt",
        "FAQ": "FAQ",
        "Inizia gratis": "Kostenlos starten",
        "Confronta i piani": "Pläne vergleichen",
        "Passa a Plus": "Auf Plus upgraden",
        "Crea account": "Konto erstellen",
        "Bentornato": "Willkommen zurück",
        "Password dimenticata?": "Passwort vergessen?",
        "Chiudi": "Schließen",
        "Mostra": "Anzeigen",
        "Nascondi": "Ausblenden",
        "Accedi": "Anmelden",
        "Registrati": "Registrieren",
        "Accesso": "Anmeldung",
        "Nome e cognome": "Vollständiger Name",
        "Hai già un account?": "Haben Sie bereits ein Konto?",
        "Nuovo su Centropic?": "Neu bei Centropic?",
        "Accetto i": "Ich akzeptiere die",
        "Termini": "Bedingungen",
        "Informativa privacy": "Datenschutzerklärung",
        "Reinvia email di conferma": "Bestätigungs-E-Mail erneut senden",
        "Resta connesso su questo dispositivo (30 giorni)": (
            "Auf diesem Gerät angemeldet bleiben (30 Tage)"
        ),
        "Principale": "Hauptnavigation",
        "Amplia copertura": "Abdeckung erweitern",
        "Copertura del piano": "Planabdeckung",
        "Copertura stimata": "Geschätzte Abdeckung",
        "Copertura insufficiente": "Unzureichende Abdeckung",
        "Copertura extra": "Zusätzliche Abdeckung",
        "Copertura residua": "Verbleibende Abdeckung",
        "Amplia la copertura del mese": "Abdeckung für diesen Monat erweitern",
        "Il": "Der",
        "Elenco prompt usati per SoV measured; personalizzabile in Impostazioni.": (
            "Prompt-Liste für Measured SoV; in den Einstellungen anpassbar."
        ),
        "Analizza il tuo dominio": "Domain analysieren",
        "URL del sito": "Website-URL",
        "Vedi un report di esempio": "Beispielreport ansehen",
        "Anteprima immediata · niente carta": "Sofortvorschau · keine Karte nötig",
    },
    "es": {
        "Sales only": "Solo ventas",
        "Waitlist": "Lista de espera",
        "In vendita": "Disponible ahora",
        "Vedi Plus": "Ver Plus",
        "Waitlist Business": "Lista de espera Business",
        "Evidence:": "Evidence:",
        "LIVE": "LIVE",
        "Prefisso internazionale": "Prefijo internacional",
        "Entra in dashboard, analizza il dominio e scarica il pack.": (
            "Entra al dashboard, analiza tu dominio y descarga el pack."
        ),
        "Quote Free esaurite · passa a Plus per continuare": (
            "Cuota Free agotada · pasa a Plus para continuar"
        ),
        "Esci": "Cerrar sesión",
        "Contatti": "Contacto",
        "Chi siamo": "Quiénes somos",
        "Guida": "Guía",
        "Storico": "Historial",
        "Impostazioni": "Ajustes",
        "Dashboard": "Dashboard",
        "Prezzi": "Precios",
        "Prodotto": "Producto",
        "FAQ": "FAQ",
        "Inizia gratis": "Empieza gratis",
        "Confronta i piani": "Compara los planes",
        "Passa a Plus": "Pasar a Plus",
        "Crea account": "Crear cuenta",
        "Bentornato": "Bienvenido de nuevo",
        "Password dimenticata?": "¿Olvidaste tu contraseña?",
        "Chiudi": "Cerrar",
        "Mostra": "Mostrar",
        "Nascondi": "Ocultar",
        "Accedi": "Iniciar sesión",
        "Registrati": "Regístrate",
        "Accesso": "Iniciar sesión",
        "Nome e cognome": "Nombre completo",
        "Hai già un account?": "¿Ya tienes una cuenta?",
        "Nuovo su Centropic?": "¿Nuevo en Centropic?",
        "Accetto i": "Acepto los",
        "Termini": "Términos",
        "Informativa privacy": "Política de privacidad",
        "Reinvia email di conferma": "Reenviar email de confirmación",
        "Resta connesso su questo dispositivo (30 giorni)": (
            "Mantener la sesión en este dispositivo (30 días)"
        ),
        "Principale": "Principal",
        "Amplia copertura": "Ampliar cobertura",
        "Copertura del piano": "Cobertura del plan",
        "Copertura stimata": "Cobertura estimada",
        "Copertura insufficiente": "Cobertura insuficiente",
        "Copertura extra": "Cobertura extra",
        "Copertura residua": "Cobertura restante",
        "Amplia la copertura del mese": "Amplía la cobertura del mes",
        "Il": "El",
        "Elenco prompt usati per SoV measured; personalizzabile in Impostazioni.": (
            "Lista de prompts usados para SoV measured; personalizable en Ajustes."
        ),
        "Analizza il tuo dominio": "Analiza tu dominio",
        "URL del sito": "URL del sitio",
        "Vedi un report di esempio": "Ver un informe de ejemplo",
        "Anteprima immediata · niente carta": "Vista previa inmediata · sin tarjeta",
        "Dashboard": "Dashboard",
    },
    "ko": {
        "Sales only": "영업 전용",
        "Waitlist": "대기자 명단",
        "In vendita": "판매 중",
        "Vedi Plus": "Plus 보기",
        "Waitlist Business": "Business 대기자 명단",
        "Evidence:": "Evidence:",
        "LIVE": "LIVE",
        "Prefisso internazionale": "국가 번호",
        "Entra in dashboard, analizza il dominio e scarica il pack.": (
            "대시보드에 로그인해 도메인을 분석하고 pack을 다운로드하세요."
        ),
        "Quote Free esaurite · passa a Plus per continuare": (
            "무료 할당량이 소진되었습니다 · 계속하려면 Plus로 업그레이드하세요"
        ),
        "Esci": "로그아웃",
        "Contatti": "문의",
        "Chi siamo": "회사 소개",
        "Guida": "가이드",
        "Storico": "기록",
        "Impostazioni": "설정",
        "Dashboard": "Dashboard",
        "Prezzi": "요금제",
        "Prodotto": "제품",
        "FAQ": "FAQ",
        "Inizia gratis": "무료로 시작하기",
        "Confronta i piani": "요금제 비교",
        "Passa a Plus": "Plus로 업그레이드",
        "Crea account": "계정 만들기",
        "Bentornato": "다시 오신 것을 환영합니다",
        "Password dimenticata?": "비밀번호를 잊으셨나요?",
        "Chiudi": "닫기",
        "Mostra": "표시",
        "Nascondi": "숨기기",
        "Accedi": "로그인",
        "Registrati": "회원가입",
        "Accesso": "로그인",
        "Nome e cognome": "이름",
        "Hai già un account?": "이미 계정이 있으신가요?",
        "Nuovo su Centropic?": "Centropic이 처음이신가요?",
        "Accetto i": "다음에 동의합니다",
        "Termini": "이용약관",
        "Informativa privacy": "개인정보 처리방침",
        "Reinvia email di conferma": "확인 이메일 다시 보내기",
        "Resta connesso su questo dispositivo (30 giorni)": (
            "이 기기에서 로그인 상태 유지 (30일)"
        ),
        "Principale": "주 메뉴",
        "Amplia copertura": "커버리지 확대",
        "Copertura del piano": "플랜 커버리지",
        "Copertura stimata": "예상 커버리지",
        "Copertura insufficiente": "커버리지 부족",
        "Copertura extra": "추가 커버리지",
        "Copertura residua": "남은 커버리지",
        "Amplia la copertura del mese": "이번 달 커버리지 확대",
        "Il": "이",
        "Elenco prompt usati per SoV measured; personalizzabile in Impostazioni.": (
            "Measured SoV에 사용된 프롬프트 목록; 설정에서 맞춤 가능."
        ),
        "Analizza il tuo dominio": "도메인 분석",
        "URL del sito": "사이트 URL",
        "Vedi un report di esempio": "샘플 리포트 보기",
        "Anteprima immediata · niente carta": "즉시 미리보기 · 카드 불필요",
    },
    "zh_Hans": {
        "Sales only": "仅限销售开通",
        "Waitlist": "候补名单",
        "In vendita": "现已发售",
        "Vedi Plus": "查看 Plus",
        "Waitlist Business": "Business 候补名单",
        "Evidence:": "Evidence:",
        "LIVE": "LIVE",
        "Prefisso internazionale": "国际区号",
        "Entra in dashboard, analizza il dominio e scarica il pack.": (
            "登录控制台，分析您的域名并下载 pack。"
        ),
        "Quote Free esaurite · passa a Plus per continuare": (
            "免费额度已用完 · 升级到 Plus 以继续"
        ),
        "Esci": "退出登录",
        "Contatti": "联系",
        "Chi siamo": "关于我们",
        "Guida": "指南",
        "Storico": "历史记录",
        "Impostazioni": "设置",
        "Dashboard": "控制台",
        "Prezzi": "定价",
        "Prodotto": "产品",
        "FAQ": "FAQ",
        "Inizia gratis": "免费开始",
        "Confronta i piani": "比较方案",
        "Passa a Plus": "升级到 Plus",
        "Crea account": "创建账户",
        "Bentornato": "欢迎回来",
        "Password dimenticata?": "忘记密码？",
        "Chiudi": "关闭",
        "Mostra": "显示",
        "Nascondi": "隐藏",
        "Accedi": "登录",
        "Registrati": "注册",
        "Accesso": "登录",
        "Nome e cognome": "姓名",
        "Hai già un account?": "已有账户？",
        "Nuovo su Centropic?": "首次使用 Centropic？",
        "Accetto i": "我同意",
        "Termini": "条款",
        "Informativa privacy": "隐私政策",
        "Reinvia email di conferma": "重新发送确认邮件",
        "Resta connesso su questo dispositivo (30 giorni)": (
            "在此设备保持登录（30 天）"
        ),
        "Principale": "主导航",
        "Amplia copertura": "增加额度",
        "Copertura del piano": "方案额度",
        "Copertura stimata": "预计额度",
        "Copertura insufficiente": "额度不足",
        "Copertura extra": "额外额度",
        "Copertura residua": "剩余额度",
        "Amplia la copertura del mese": "增加本月额度",
        "Il": "该",
        "Elenco prompt usati per SoV measured; personalizzabile in Impostazioni.": (
            "用于 Measured SoV 的提示词列表；可在设置中自定义。"
        ),
        "Analizza il tuo dominio": "分析您的域名",
        "URL del sito": "网站 URL",
        "Vedi un report di esempio": "查看示例报告",
        "Anteprima immediata · niente carta": "即时预览 · 无需银行卡",
    },
}


def load_maps() -> dict[str, dict[str, str]]:
    en_de = json.loads((WORK / "en_de.json").read_text(encoding="utf-8"))
    es_ko = json.loads((WORK / "es_ko_zh.json").read_text(encoding="utf-8"))
    maps = {
        "en": dict(en_de["en"]),
        "de": dict(en_de["de"]),
        "es": dict(es_ko["es"]),
        "ko": dict(es_ko["ko"]),
        "zh_Hans": dict(es_ko["zh_Hans"]),
    }
    for loc, extras in EXTRA.items():
        maps[loc].update(extras)
    # Fill any blanks from English.
    for loc in maps:
        for key, val in list(maps[loc].items()):
            if not (val or "").strip():
                maps[loc][key] = maps["en"].get(key, key)
    return maps


def apply_locale(loc: str, mapping: dict[str, str]) -> tuple[int, int]:
    path = ROOT / "translations" / loc / "LC_MESSAGES" / "messages.po"
    with path.open("rb") as fh:
        cat: Catalog = read_po(fh)
    updated = 0
    unfuzzied = 0
    for msg in cat:
        if not msg.id:
            continue
        key = msg.id if isinstance(msg.id, str) else msg.id[0]
        if key not in mapping:
            continue
        new = mapping[key]
        old = msg.string if isinstance(msg.string, str) else (
            msg.string[0] if msg.string else ""
        )
        if old != new:
            msg.string = new
            updated += 1
        if "fuzzy" in msg.flags:
            msg.flags.discard("fuzzy")
            unfuzzied += 1
    with path.open("wb") as fh:
        write_po(fh, cat, ignore_obsolete=False, include_previous=False, width=80)
    return updated, unfuzzied


def main() -> None:
    maps = load_maps()
    for loc, mapping in maps.items():
        u, f = apply_locale(loc, mapping)
        print(f"{loc}: updated={u} unfuzzied={f} map_keys={len(mapping)}")


if __name__ == "__main__":
    main()
