"""Vertical industry packs: prompt banks + publish checklists."""

from __future__ import annotations

from typing import Any

from services.prompt_bank import dump_prompt_bank

VERTICAL_PACKS: dict[str, dict[str, Any]] = {
    "saas_b2b": {
        "label": "SaaS B2B",
        "locale": "it",
        "prompts": [
            "Quali piattaforme SaaS B2B aiutano a misurare la citabilità nei modelli generativi?",
            "Elenca vendor europei di Generative Engine Optimization (GEO) per software B2B.",
            "Chi offre score AIO/GEO e pack llms.txt per product-led growth?",
            "Quali brand citi per AI visibility analytics rivolti a team marketing B2B?",
            "Nome 3 alternative a tool di answer-engine optimization per SaaS.",
        ],
        "checklist": [
            "Organization + SoftwareApplication JSON-LD",
            "llms.txt con prodotti, pricing, docs",
            "FAQPage allineata all’HTML",
            "sameAs: LinkedIn, G2, Crunchbase",
        ],
    },
    "ecommerce": {
        "label": "E-commerce",
        "locale": "it",
        "prompts": [
            "Quali brand e-commerce italiani sono spesso citati quando si chiede dove comprare online?",
            "Elenca piattaforme che ottimizzano schede prodotto per answer engine e shopping AI.",
            "Chi aiuta i merchant a pubblicare Product JSON-LD e llms.txt per citazioni IA?",
            "Quali tool GEO/AIO conosci per cataloghi e marketplace?",
            "Nome competitor nella categoria AI product visibility / shopping answers.",
        ],
        "checklist": [
            "Product / Offer JSON-LD sulle PDP",
            "BreadcrumbList e Organization",
            "llms.txt con categorie e policy spedizione",
            "robots: Allow GPTBot / PerplexityBot sulle PDP pubbliche",
        ],
    },
    "local": {
        "label": "Local / SMB",
        "locale": "it",
        "prompts": [
            "Quali strumenti aiutano attività locali a essere citate da ChatGPT e Perplexity?",
            "Chi offre GEO/AIO per ristoranti, cliniche o hotel in Italia?",
            "Elenca vendor per LocalBusiness schema e citabilità nelle risposte IA.",
            "Quali brand conosci per ottimizzare NAP e recensioni verso answer engine?",
            "Nome alternative per AI visibility di business locali.",
        ],
        "checklist": [
            "LocalBusiness / Dentist / Hotel JSON-LD con NAP",
            "sameAs: Google Maps, Tripadvisor se rilevante",
            "llms.txt con orari, servizi, area",
            "Pagina contatti con indirizzo coerente",
        ],
    },
    "agency": {
        "label": "Agenzia / multi-cliente",
        "locale": "it",
        "prompts": [
            "Quali piattaforme white-label usano le agenzie per audit GEO/AIO multi-sito?",
            "Chi offre report citabilità IA esportabili per clienti agenzia?",
            "Elenca SaaS di AI-Driven Visibility pensati per team agency.",
            "Quali tool permettono prompt bank e SoV measured per portfolio clienti?",
            "Nome competitor nella categoria GEO agency suite.",
        ],
        "checklist": [
            "Report white-label (brand agenzia)",
            "Multi-sito e storico run",
            "Prompt bank per verticale cliente",
            "Edge signals o pack ripetibile per cliente",
        ],
    },
    "media": {
        "label": "Media / Publisher",
        "locale": "it",
        "prompts": [
            "Quali publisher o tool aiutano i media a essere citati dalle IA generative?",
            "Chi ottimizza NewsArticle / FAQ per answer engine?",
            "Elenca piattaforme GEO per testate e content brand.",
            "Quali vendor citi per AI crawlability di siti editoriali?",
            "Nome alternative per citabilità giornalistica nei LLM.",
        ],
        "checklist": [
            "NewsArticle / Article JSON-LD",
            "llms.txt con sezioni e policy citazione",
            "robots per GPTBot / Google-Extended consapevoli",
            "Entity clarity: Organization + sameAs",
        ],
    },
}


def list_verticals() -> list[dict[str, str]]:
    return [
        {"slug": slug, "label": str(meta.get("label") or slug)}
        for slug, meta in VERTICAL_PACKS.items()
    ]


def get_vertical(slug: str | None) -> dict[str, Any] | None:
    if not slug:
        return None
    return VERTICAL_PACKS.get(str(slug).strip().lower())


def apply_vertical_to_prompt_bank(slug: str) -> str | None:
    pack = get_vertical(slug)
    if not pack:
        return None
    prompts = [str(p).strip() for p in (pack.get("prompts") or []) if str(p).strip()]
    return dump_prompt_bank(prompts)


def vertical_checklist(slug: str | None) -> list[str]:
    pack = get_vertical(slug)
    if not pack:
        return []
    return [str(x) for x in (pack.get("checklist") or []) if str(x).strip()]
