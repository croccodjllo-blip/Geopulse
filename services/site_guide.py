"""Complete Centropic site guide + glossary (single source of truth)."""

from __future__ import annotations

from typing import Any


def _glossary_entries() -> list[dict[str, str]]:
    raw = [
        ("aio", "AIO", "AI-Driven Visibility: quanto brand e sito sono comprensibili/visibili a modelli e crawler IA. Non significa All-in-One."),
        ("geo", "GEO", "Generative Engine Optimization: ottimizzazione per essere citati nelle risposte generate da answer engine. Non significa GIS."),
        ("sov", "SoV (Share of Voice)", "Quota di “voce” del brand rispetto agli engine. Proxy = stimato; Measured = campionato via citation monitor (Plus)."),
        ("misurato", "Misurato", "Segnale osservato direttamente (probe HTTP/HTML) o menzione contata via API LLM configurate."),
        ("stimato", "Stimato (proxy)", "Valore euristico derivato dai segnali del sito, non una citazione live nella UI dell’LLM."),
        ("indice", "Indice DDD→AAA", "Scala sintetica della qualità AIO/GEO complessiva, da critica (DDD) a eccellente (AAA)."),
        ("finding", "Finding", "Singolo gap o conferma (critical / warn / ok) con contesto e priorità."),
        ("pack", "Pack", "Insieme di artifact generati dall’analisi (llms, schema, meta, robots, checklist)."),
        ("llms-txt", "llms.txt", "File root machine-readable che spiega brand, topic e URL preferiti ai modelli/crawler IA."),
        ("json-ld", "JSON-LD", "Dati strutturati Schema.org incorporati in pagina (Organization, FAQPage, …)."),
        ("edge-signals", "Edge Signals", "Endpoint Centropic /e/<token>/… che servono artifact aggiornati dinamicamente."),
        ("cms-connector", "CMS Connector", "Pacchetto universale (plugin/rewrite) che punta i path AIO del tuo dominio verso Edge."),
        ("signals-json", "signals.json", "Payload macchina con versioning e metadati Edge per discovery e integrazioni."),
        ("citation-monitor", "Citation monitor", "Job Plus che invia prompt bank agli LLM e misura menzioni del brand."),
        ("prompt-bank", "Prompt bank", "Elenco prompt usati per SoV measured; personalizzabile in Impostazioni."),
        ("vertical-pack", "Vertical pack", "Set di prompt/checklist per settore (es. SaaS, local, ecommerce)."),
        ("publish-verify", "Publish verify", "Controllo che gli artifact pubblicati sul dominio siano raggiungibili e coerenti."),
        ("entity-graph", "Entity graph", "Rete di segnali entity (nome, sameAs, contatti) che disambiguano il brand."),
        ("citability", "Citability", "Quanto il contenuto è facilmente citabile da un modello (chiarezza, fatti, struttura)."),
        ("schema-quality", "Schema quality", "Completezza e correttezza dei dati strutturati sul sito."),
        ("crawler-ia", "Crawler IA", "Bot come GPTBot, ClaudeBot, PerplexityBot, Google-Extended che indicizzano per modelli."),
        ("robots-txt", "robots.txt", "Policy di accesso crawler; bozza Centropic apre i bot IA utili senza spezzare le regole esistenti."),
        ("geo-token", "GEO token", "Unità di credito prodotto (1 token = €0,10). Consumata da analisi e job measured."),
        ("hold", "Hold", "Prenotazione temporanea di credito prima di un job; rilasciata o convertita a debito a fine run."),
        ("re-scan", "Re-scan", "Nuova analisi dello stesso sito, manuale o schedulata (Plus)."),
        ("white-label", "White-label", "Report esportabile con brand agenzia (logo/colori) per clienti finali."),
        ("api-key", "API key (gp_…)", "Chiave Bearer per /api/v1 (analyze, sites, edge). Solo Plus."),
        ("engine-breakdown", "Engine breakdown", "Vista per motore (ChatGPT, Gemini*, Claude, Perplexity, Grok, Azure*) dello Share of Voice."),
        ("pagine-critiche", "Pagine critiche", "URL del crawl con gap gravi che trascinano score o citabilità."),
        ("before-after", "before-after.md", "Documento pack che confronta due run successive dopo fix."),
    ]
    return [
        {"slug": slug, "term": term, "definition": definition}
        for slug, term, definition in raw
    ]


# Illustrations under static/img/guide/
GUIDE_IMAGES = {
    "dashboard": "img/guide/dashboard.svg",
    "analisi": "img/guide/analisi-aio-geo.svg",
    "findings": "img/guide/findings.svg",
    "pack": "img/guide/pack-artifact.svg",
    "edge": "img/guide/edge-signals.svg",
    "cms": "img/guide/cms-connector.svg",
    "sov": "img/guide/sov-citation.svg",
    "geo_suite": "img/guide/geo-suite.svg",
    "competitors": "img/guide/competitors.svg",
    "storico": "img/guide/storico-rescan.svg",
    "tokens": "img/guide/token-crediti.svg",
    "api": "img/guide/api-whitelabel.svg",
}


def site_guide_payload() -> dict[str, Any]:
    """Structured content for /guida and /dashboard/guida."""
    return {
        "title": "Guida completa Centropic",
        "lede": (
            "Tutto il prodotto in un’unica pagina: analisi AIO/GEO, moduli diagnostici, "
            "pack, Edge Signals, CMS, token, API e glossario."
        ),
        "updated": "4 agosto 2026",
        "toc": [
            {"id": "introduzione", "label": "Introduzione"},
            {"id": "servizi", "label": "Servizi"},
            {"id": "analisi", "label": "Analisi e moduli"},
            {"id": "dopo-analisi", "label": "Dopo l’analisi"},
            {"id": "pack", "label": "Pack e file"},
            {"id": "edge-cms", "label": "Edge e CMS"},
            {"id": "piani", "label": "Piani e token"},
            {"id": "glossario", "label": "Glossario"},
        ],
        "services": [
            {
                "id": "svc-dashboard",
                "title": "Dashboard",
                "image": GUIDE_IMAGES["dashboard"],
                "summary": "Workspace unico: ultima analisi, score, findings, SoV e azioni.",
                "bullets": [
                    "Avvia o ripeti l’analisi sull’URL del sito",
                    "Vedi Indice DDD→AAA, score AIO/GEO e Share of Voice",
                    "Accedi a pack, Edge Signals, storico e crediti",
                ],
            },
            {
                "id": "svc-analisi",
                "title": "Analisi AIO / GEO",
                "image": GUIDE_IMAGES["analisi"],
                "summary": "Probe HTTP + parsing HTML sul dominio: misurato ciò che è osservabile.",
                "bullets": [
                    "AIO = AI-Driven Visibility (quanto i modelli “vedono” il brand)",
                    "GEO = Generative Engine Optimization (citabilità nelle risposte generate)",
                    "Indice lettera DDD→AAA sintetizza la qualità complessiva",
                ],
            },
            {
                "id": "svc-findings",
                "title": "Findings e pagine critiche",
                "image": GUIDE_IMAGES["findings"],
                "summary": "Gap prioritizzati: critical, warn, ok — con azioni concrete.",
                "bullets": [
                    "Chiudi prima i critical (es. bot IA bloccati in robots)",
                    "Usa fix-this-week.md come checklist operativa",
                    "Le pagine critiche evidenziano URL con gap gravi",
                ],
            },
            {
                "id": "svc-pack",
                "title": "Pack ottimizzazione",
                "image": GUIDE_IMAGES["pack"],
                "summary": "Artifact pronti: llms.txt, JSON-LD, FAQ, meta, robots, before/after.",
                "bullets": [
                    "Copia dai pannelli o scarica lo ZIP",
                    "Su Plus puoi inviare il pack via email",
                    "La pubblicazione sul sito resta a tuo carico (o via Edge/CMS)",
                ],
            },
            {
                "id": "svc-edge",
                "title": "Edge Signals",
                "image": GUIDE_IMAGES["edge"],
                "summary": "Hosting dinamico degli artifact su centropic.ai/e/<token>/…",
                "bullets": [
                    "Free: llms.txt + signals.json",
                    "Plus: robots live, organization.jsonld, Worker/Vercel/embed",
                    "Si aggiorna a ogni re-scan e quando cambia la lista crawler IA",
                ],
            },
            {
                "id": "svc-cms",
                "title": "CMS Connector universale",
                "image": GUIDE_IMAGES["cms"],
                "summary": "Un ZIP per WordPress, Drupal, Shopify, PHP, Netlify, Cloudflare, Vercel.",
                "bullets": [
                    "Attiva Edge, poi scarica il connector dalla dashboard",
                    "Un solo adapter sul tuo host: proxy verso Edge",
                    "API: GET /api/v1/sites/<id>/edge",
                ],
            },
            {
                "id": "svc-sov",
                "title": "Share of Voice",
                "image": GUIDE_IMAGES["sov"],
                "summary": "Proxy (stimato) su tutti i piani; measured solo su Plus con citation monitor.",
                "bullets": [
                    "Stimato: euristiche su segnali del sito",
                    "Misurato: prompt bank → menzioni brand nelle risposte LLM",
                    "Gemini e Azure AI restano proxy onesti (non Overview/Copilot nativi)",
                ],
            },
            {
                "id": "svc-geo",
                "title": "GEO Suite",
                "image": GUIDE_IMAGES["geo_suite"],
                "summary": "Moduli: entity graph, citability, schema, publish verify, llms lint, locales.",
                "bullets": [
                    "Entity: Organization, sameAs, contatti",
                    "Publish verify: controlla se gli artifact sono live",
                    "Locales: hreflang e coerenza mercati",
                ],
            },
            {
                "id": "svc-comp",
                "title": "Competitor snapshot",
                "image": GUIDE_IMAGES["competitors"],
                "summary": "Confronto rapido AIO/GEO/rating sui competitor (Plus).",
                "bullets": [
                    "Stesse metriche del tuo sito",
                    "Utile per priorità relative, non ranking assoluto",
                ],
            },
            {
                "id": "svc-storico",
                "title": "Storico e re-scan",
                "image": GUIDE_IMAGES["storico"],
                "summary": "Cronologia run, trend e schedulazione automatica (Plus).",
                "bullets": [
                    "before-after.md confronta due analisi",
                    "Imposta frequenza e orario UTC in Impostazioni",
                    "Storico esteso sul piano Plus",
                ],
            },
            {
                "id": "svc-tokens",
                "title": "Token GEO e crediti",
                "image": GUIDE_IMAGES["tokens"],
                "summary": "Le analisi e il SoV measured consumano token; i pack ricaricano il saldo.",
                "bullets": [
                    "1 GEO token = €0,10 (ledger in centesimi)",
                    "Pack €10→100, €20→200, €50→600 (bonus)",
                    "Plus €14,99/mese include 100 token per ciclo pagato",
                ],
            },
            {
                "id": "svc-api",
                "title": "API e white-label",
                "image": GUIDE_IMAGES["api"],
                "summary": "Automazione agenzia: API key, analyze, sites, edge; report white-label.",
                "bullets": [
                    "Bearer gp_… su /api/v1/*",
                    "Export report MD/HTML con brand agenzia",
                    "Riservato al piano Plus",
                ],
            },
        ],
        "analyses": [
            {
                "title": "Crawl e probe",
                "body": (
                    "Centropic richiede title, meta, JSON-LD, FAQ, robots, llms.txt, sitemap, "
                    "ai.txt, humans.txt e pagine del sito. Free: tetto pagine; Plus: crawl intero "
                    "(con tetto operativo di piattaforma)."
                ),
            },
            {
                "title": "Engine breakdown",
                "body": (
                    "Vista per ChatGPT, Gemini (proxy AI Overview), Claude, Perplexity, Grok e "
                    "Azure AI. Di default è Stimato; con SoV measured gli engine disponibili "
                    "passano a Misurato."
                ),
            },
            {
                "title": "Entity graph",
                "body": (
                    "Valuta coerenza Organization / brand, sameAs, contatti e segnali entity "
                    "riutilizzabili da crawler e modelli."
                ),
            },
            {
                "title": "Citability",
                "body": (
                    "Quanto il copy è citabile: claim chiari, definizioni, fatti verificabili, "
                    "meno ambiguità sul “chi siete / cosa fate”."
                ),
            },
            {
                "title": "Schema quality",
                "body": (
                    "Qualità e completezza JSON-LD (Organization, WebSite, FAQPage, "
                    "SoftwareApplication, Article dove rilevante)."
                ),
            },
            {
                "title": "Publish verify",
                "body": (
                    "Verifica se llms.txt, robots e schema pubblicati sul dominio corrispondono "
                    "alle bozze del pack / Edge."
                ),
            },
            {
                "title": "llms lint",
                "body": (
                    "Controlla presenza e qualità di /llms.txt: brand, topic, URL assoluti, "
                    "preferred citation."
                ),
            },
            {
                "title": "Locales",
                "body": (
                    "Segnali hreflang / mercati: coerenza linguistica e copertura internazionale "
                    "per answer engine multi-lingua."
                ),
            },
            {
                "title": "SoV measured",
                "body": (
                    "Solo Plus: citation monitor con prompt bank. Conta menzioni brand/dominio "
                    "nelle risposte — campione probe, non garanzia di ranking nelle UI consumer."
                ),
            },
        ],
        "workflow": [
            {
                "title": "Indice DDD→AAA",
                "body": "Leggi la lettera: DDD è critico, AAA è top. Mira a salire di almeno un grado tra un re-scan e l’altro.",
            },
            {
                "title": "Score AIO / GEO",
                "body": "Sotto 60 = intervento prioritario. AIO e GEO vanno letti insieme al SoV, non isolati.",
            },
            {
                "title": "Findings",
                "body": "Chiudi critical e warn; usa fix-this-week.md. Poi ripubblica e verifica.",
            },
            {
                "title": "Pubblica llms.txt",
                "body": "Root del sito: https://tuodominio/llms.txt — oppure Edge + CMS connector.",
            },
            {
                "title": "JSON-LD + FAQ + meta",
                "body": "Incolla nel <head> delle pagine chiave (o lascia Edge servire organization.jsonld).",
            },
            {
                "title": "robots.txt",
                "body": "Unisci la bozza al file esistente; lascia aperti i bot IA utili (GPTBot, ClaudeBot, …).",
            },
            {
                "title": "Re-scan",
                "body": "Su Plus imposta frequenza/orario UTC e confronta before/after.md.",
            },
        ],
        "pack_files": [
            {"file": "llms.txt", "where": "root del sito"},
            {"file": "organization.jsonld.html", "where": "<head> o Edge /.well-known/"},
            {"file": "faq.jsonld.html", "where": "<head>"},
            {"file": "meta-pack.html", "where": "<head>"},
            {"file": "robots.txt", "where": "root del sito"},
            {"file": "fix-this-week.md", "where": "checklist operativa interna"},
            {"file": "before-after.md", "where": "confronto tra run"},
            {"file": "signals.json", "where": "Edge /geopulse/signals.json via CMS"},
        ],
        "plans": [
            {
                "name": "Free",
                "points": [
                    "1 sito, crawl pagine limitate, 2 analisi su nuovi siti (ri-analisi stesso URL ok, consuma token)",
                    "Score, findings, pack ZIP, Edge base (llms + signals)",
                    "SoV stimato (proxy)",
                ],
            },
            {
                "name": "Plus",
                "points": [
                    "Crawl fino a 120 pagine (Deep 500), multi-sito, competitor, storico esteso",
                    "SoV measured, prompt bank, re-scan, API, white-label",
                    "Edge completo + CMS connector + 100 token/ciclo",
                ],
            },
        ],
        "glossary": _glossary_entries(),
        "deep_links": [
            {"href": "/metodologia", "label": "Metodologia (Misurato vs Stimato)"},
            {"href": "/guide/llms-txt", "label": "Guida llms.txt"},
            {"href": "/guide/schema-ai", "label": "Schema.org per answer engine"},
            {"href": "/guide/score-vs-sov", "label": "Score AIO/GEO vs SoV"},
            {"href": "/faq", "label": "FAQ"},
            {"href": "/prodotto", "label": "Prodotto"},
            {"href": "/pricing", "label": "Piani e prezzi"},
        ],
    }
