"""Legal document helpers: Art. 28 DPA + sub-processor register."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any


DPA_VERSION = "2026-08-12"
DPA_LAST_UPDATED = date(2026, 8, 12)

# Digital-service waiver (consumer withdrawal / immediate performance)
DIGITAL_WAIVER_VERSION = "2026-08-12"


@dataclass(frozen=True)
class SubProcessor:
    name: str
    role: str
    data_categories: str
    location: str
    docs_url: str
    active: bool = True


def _env_set(*names: str) -> bool:
    return any((os.getenv(n) or "").strip() for n in names)


def sub_processors() -> list[SubProcessor]:
    """Active + always-listed processors for Centropic SaaS."""
    rows = [
        SubProcessor(
            name="Paddle.com Market Limited",
            role="Merchant of record / pagamenti (titolare autonomo per billing)",
            data_categories="Email, identificativi cliente/transazione, importi, stato abbonamento",
            location="UE / UK (Paddle)",
            docs_url="https://www.paddle.com/legal/privacy",
            active=_env_set("PADDLE_API_KEY", "PADDLE_CLIENT_TOKEN", "PADDLE_PRICE_PLUS_MONTHLY"),
        ),
        SubProcessor(
            name="Hosting VPS (IONOS / infrastruttura Centropic)",
            role="Hosting applicazione, database, log tecnici",
            data_categories="Account, siti analizzati, risultati, log IP/timestamp",
            location="UE (Germania / EU region)",
            docs_url="https://www.ionos.com/terms-gtc/privacy-policy/",
            active=True,
        ),
        SubProcessor(
            name="Object storage S3-compatible (MinIO / AWS S3)",
            role="Archiviazione pack/artifact analisi",
            data_categories="Artifact HTML/testo generati, metadati job",
            location="UE (configurabile via endpoint)",
            docs_url="https://aws.amazon.com/privacy/",
            active=_env_set("ANALYZE_S3_BUCKET", "ANALYZE_S3_ENDPOINT_URL"),
        ),
        SubProcessor(
            name="Redis",
            role="Coda job / rate limit / cache operativa",
            data_categories="Identificativi job, contatori, slot temporanei",
            location="Stesso host / rete privata UE",
            docs_url="",
            active=_env_set("REDIS_URL"),
        ),
        SubProcessor(
            name="Email transazionale (SMTP / Resend)",
            role="Invio email account, pack, alert",
            data_categories="Email destinatario, contenuto messaggi transazionali",
            location="UE o USA a seconda del provider configurato",
            docs_url="https://resend.com/legal/privacy-policy",
            active=_env_set("SMTP_HOST", "RESEND_API_KEY"),
        ),
        SubProcessor(
            name="OpenAI, LLC",
            role="LLM per artifact / citation monitor (se abilitato)",
            data_categories="Prompt, snippet pagine pubbliche, output modello",
            location="USA / regioni OpenAI",
            docs_url="https://openai.com/policies/privacy-policy",
            active=_env_set("OPENAI_API_KEY"),
        ),
        SubProcessor(
            name="Anthropic, PBC",
            role="LLM citation monitor (se abilitato)",
            data_categories="Prompt, snippet pagine pubbliche, output modello",
            location="USA",
            docs_url="https://www.anthropic.com/legal/privacy",
            active=_env_set("ANTHROPIC_API_KEY"),
        ),
        SubProcessor(
            name="Perplexity AI, Inc.",
            role="LLM citation monitor (se abilitato)",
            data_categories="Prompt, snippet pagine pubbliche, output modello",
            location="USA",
            docs_url="https://www.perplexity.ai/privacy",
            active=_env_set("PERPLEXITY_API_KEY"),
        ),
        SubProcessor(
            name="Google LLC (Gemini / Analytics)",
            role="LLM Gemini e/o GA4 misurazione (consenso cookie)",
            data_categories="Prompt LLM e/o dati misurazione web se consenso",
            location="USA / UE (Google Cloud)",
            docs_url="https://policies.google.com/privacy",
            active=_env_set("GEMINI_API_KEY", "GOOGLE_API_KEY", "GA4_MEASUREMENT_ID"),
        ),
        SubProcessor(
            name="xAI",
            role="LLM citation monitor (se abilitato)",
            data_categories="Prompt, snippet pagine pubbliche, output modello",
            location="USA",
            docs_url="https://x.ai/legal/privacy-policy",
            active=_env_set("XAI_API_KEY"),
        ),
        SubProcessor(
            name="Sentry",
            role="Error tracking applicativo (se abilitato)",
            data_categories="Stack trace, ID richiesta; evitare PII in log",
            location="UE / USA a seconda del progetto",
            docs_url="https://sentry.io/privacy/",
            active=_env_set("SENTRY_DSN"),
        ),
    ]
    return rows


def active_sub_processors() -> list[SubProcessor]:
    return [r for r in sub_processors() if r.active]


def dpa_context(*, company_name: str, company_email: str = "info@centropic.ai") -> dict[str, Any]:
    return {
        "dpa_version": DPA_VERSION,
        "dpa_last_updated": DPA_LAST_UPDATED.isoformat(),
        "dpa_company_name": company_name or "Engineering Factory",
        "dpa_contact_email": company_email,
        "sub_processors": active_sub_processors(),
        "sub_processors_all": sub_processors(),
    }


def render_dpa_plaintext(*, company_name: str, company_email: str = "info@centropic.ai") -> str:
    """Procurement-friendly plain-text DPA + sub-processor annex."""
    ctx = dpa_context(company_name=company_name, company_email=company_email)
    lines = [
        "DATA PROCESSING AGREEMENT (Art. 28 GDPR)",
        f"Product: Centropic (centropic.ai)",
        f"Processor / Provider: {ctx['dpa_company_name']}",
        f"Version: {ctx['dpa_version']} · Updated: {ctx['dpa_last_updated']}",
        f"Contact: {ctx['dpa_contact_email']}",
        "",
        "1. Parties and roles",
        "The Customer (Controller) uses Centropic SaaS. The Provider acts as Processor",
        "for personal data processed to deliver the service (account data, analyzed public",
        "URLs, analysis results, technical logs). Payment card data is processed by Paddle",
        "as merchant of record (independent controller for billing).",
        "",
        "2. Subject matter and duration",
        "Processing is limited to providing Centropic features (crawl of public pages,",
        "scoring, packs, Edge signals, citation probes when entitled) for the term of the",
        "Customer's account and the retention periods in the Privacy Policy.",
        "",
        "3. Nature and purpose",
        "Hosting, analysis of Customer-submitted public URLs, generation of artifacts,",
        "optional LLM probes, email transactional delivery, security logging, support.",
        "",
        "4. Types of personal data and data subjects",
        "Account holders and invited users: name, email, company/role (optional), phone/country",
        "(optional), hashed password, plan/billing identifiers from Paddle, usage credits.",
        "Technical: IP, timestamps, session identifiers. Site content crawled is public web",
        "content submitted by Customer; Customer warrants it has rights to analyze it.",
        "",
        "5. Provider obligations (Art. 28)",
        "- process only on documented Customer instructions (use of the SaaS);",
        "- ensure confidentiality of authorized persons;",
        "- implement appropriate technical and organizational security measures;",
        "- engage sub-processors listed in Annex A (and material updates notified);",
        "- assist with data subject rights, DPIA and breach notification where applicable;",
        "- delete or return personal data after account closure, subject to legal retention;",
        "- make available information necessary to demonstrate compliance.",
        "",
        "6. International transfers",
        "Where sub-processors process outside the EEA/UK, transfers rely on appropriate",
        "safeguards (e.g. SCCs / adequacy) as described by each provider. Customer may",
        "request the current transfer summary via the contact email above.",
        "",
        "7. Customer obligations",
        "Customer is Controller for data it uploads or causes to be processed, configures",
        "access, and must not submit special-category data unless a separate written addendum",
        "is agreed. Customer must not use Centropic to scan systems without authorization.",
        "",
        "8. Liability and precedence",
        "This DPA supplements the Terms of Service and Privacy Policy. In case of conflict",
        "on data-protection obligations, this DPA prevails for processing topics. Governing",
        "law follows the Terms, without prejudice to mandatory data-protection rules.",
        "",
        "9. Acceptance",
        "Using Centropic Business / agency features, or signing an order that references this",
        "DPA version, constitutes acceptance of this DPA. A countersigned copy is available",
        f"on request to {ctx['dpa_contact_email']}.",
        "",
        "ANNEX A — Sub-processors (active configuration)",
        "",
    ]
    for sp in ctx["sub_processors"]:
        lines.append(f"- {sp.name}")
        lines.append(f"  Role: {sp.role}")
        lines.append(f"  Data: {sp.data_categories}")
        lines.append(f"  Location: {sp.location}")
        if sp.docs_url:
            lines.append(f"  Docs: {sp.docs_url}")
        lines.append("")
    if not ctx["sub_processors"]:
        lines.append("(none detected in current environment)")
        lines.append("")
    lines.append(f"End of DPA {ctx['dpa_version']}")
    lines.append("")
    return "\n".join(lines)



# Public policy versions (changelog surface)
POLICY_VERSIONS: dict[str, str] = {
    "privacy": "2026-08-12",
    "terms": "2026-08-12",
    "refunds": "2026-07-30",
    "dpa": DPA_VERSION,
    "cookies": "2026-08-12",
    "ai": "2026-08-12",
    "trust": "2026-08-12",
    "accessibility": "2026-08-12",
}


@dataclass(frozen=True)
class CookieRow:
    name: str
    provider: str
    purpose: str
    duration: str
    category: str  # necessary | analytics | advertising


def cookie_inventory(*, analytics_active: bool, ads_active: bool) -> list[CookieRow]:
    rows = [
        CookieRow(
            name="session",
            provider="Centropic",
            purpose="Sessione autenticata / CSRF",
            duration="Sessione / configurazione app",
            category="necessary",
        ),
        CookieRow(
            name="centropic_lang",
            provider="Centropic",
            purpose="Preferenza lingua UI",
            duration="1 anno",
            category="necessary",
        ),
        CookieRow(
            name="centropic_consent_v1",
            provider="Centropic (localStorage)",
            purpose="Memorizza scelta consenso analytics/ads",
            duration="Persistente (browser)",
            category="necessary",
        ),
    ]
    if analytics_active:
        rows.append(
            CookieRow(
                name="_ga / _ga_*",
                provider="Google Analytics 4",
                purpose="Misurazione traffico (solo con consenso analytics)",
                duration="Fino a 24 mesi (policy Google)",
                category="analytics",
            )
        )
    if ads_active:
        rows.append(
            CookieRow(
                name="_gcl_* / IDE (eventuali)",
                provider="Google Ads / AdSense",
                purpose="Misurazione e annunci (solo con consenso ads)",
                duration="Secondo policy Google",
                category="advertising",
            )
        )
    rows.append(
        CookieRow(
            name="fonts.googleapis.com / fonts.gstatic.com",
            provider="Google Fonts",
            purpose="Caricamento font tipografici (richiesta di rete terze parti)",
            duration="Cache browser",
            category="necessary",
        )
    )
    return rows


def legal_nav_links() -> list[dict[str, str]]:
    """Stable public legal routes for footer / trust pages."""
    return [
        {"endpoint": "privacy", "label_it": "Privacy"},
        {"endpoint": "terms", "label_it": "Termini"},
        {"endpoint": "cookies_policy", "label_it": "Cookie"},
        {"endpoint": "refunds", "label_it": "Rimborsi"},
        {"endpoint": "dpa", "label_it": "DPA"},
        {"endpoint": "ai_transparency", "label_it": "AI / LLM"},
        {"endpoint": "trust_security", "label_it": "Trust"},
        {"endpoint": "accessibility_statement", "label_it": "Accessibilità"},
    ]
 (fix(billing): enforce Plus immediate-delivery waiver on checkout)
