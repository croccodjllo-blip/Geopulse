"""Complete Centropic site guide + glossary (single source of truth)."""

from __future__ import annotations

from typing import Any

from flask_babel import gettext as _


def _glossary_entries() -> list[dict[str, str]]:
    raw = [
        (
            "aio",
            "AIO",
            _(
                "AI-Driven Visibility: quanto brand e sito sono comprensibili/visibili a modelli e crawler IA. Non significa All-in-One."
            ),
        ),
        (
            "geo",
            "GEO",
            _(
                "Generative Engine Optimization: ottimizzazione per essere citati nelle risposte generate da answer engine. Non significa GIS."
            ),
        ),
        (
            "sov",
            _("SoV (Share of Voice)"),
            _(
                "Quota di “voce” del brand rispetto agli engine. Proxy = stimato; Measured = campionato via citation monitor (Plus)."
            ),
        ),
        (
            "misurato",
            _("Misurato"),
            _(
                "Segnale osservato direttamente (probe HTTP/HTML) o menzione contata via API LLM configurate."
            ),
        ),
        (
            "stimato",
            _("Stimato (proxy)"),
            _(
                "Valore euristico derivato dai segnali del sito, non una citazione live nella UI dell’LLM."
            ),
        ),
        (
            "indice",
            _("Indice DDD→AAA"),
            _(
                "Scala sintetica della qualità AIO/GEO complessiva, da critica (DDD) a eccellente (AAA)."
            ),
        ),
        (
            "finding",
            "Finding",
            _(
                "Singolo gap o conferma (critical / warn / ok) con contesto e priorità."
            ),
        ),
        (
            "pack",
            "Pack",
            _(
                "Insieme di artifact generati dall’analisi (llms, schema, meta, robots, checklist)."
            ),
        ),
        (
            "llms-txt",
            "llms.txt",
            _(
                "File root machine-readable che spiega brand, topic e URL preferiti ai modelli/crawler IA."
            ),
        ),
        (
            "json-ld",
            "JSON-LD",
            _(
                "Dati strutturati Schema.org incorporati in pagina (Organization, FAQPage, …)."
            ),
        ),
        (
            "edge-signals",
            "Edge Signals",
            _(
                "Endpoint Centropic /e/<token>/… che servono artifact aggiornati dinamicamente."
            ),
        ),
        (
            "cms-connector",
            "CMS Connector",
            _(
                "Pacchetto universale (plugin/rewrite) che punta i path AIO del tuo dominio verso Edge."
            ),
        ),
        (
            "signals-json",
            "signals.json",
            _(
                "Payload macchina con versioning e metadati Edge per discovery e integrazioni."
            ),
        ),
        (
            "citation-monitor",
            "Citation monitor",
            _(
                "Job Plus che invia prompt bank agli LLM e misura menzioni del brand."
            ),
        ),
        (
            "prompt-bank",
            "Prompt bank",
            _(
                "Elenco prompt usati per SoV measured; personalizzabile in Impostazioni."
            ),
        ),
        (
            "vertical-pack",
            "Vertical pack",
            _(
                "Set di prompt/checklist per settore (es. SaaS, local, ecommerce)."
            ),
        ),
        (
            "publish-verify",
            "Publish verify",
            _(
                "Controllo che gli artifact pubblicati sul dominio siano raggiungibili e coerenti."
            ),
        ),
        (
            "entity-graph",
            "Entity graph",
            _(
                "Rete di segnali entity (nome, sameAs, contatti) che disambiguano il brand."
            ),
        ),
        (
            "citability",
            "Citability",
            _(
                "Quanto il contenuto è facilmente citabile da un modello (chiarezza, fatti, struttura)."
            ),
        ),
        (
            "schema-quality",
            "Schema quality",
            _(
                "Completezza e correttezza dei dati strutturati sul sito."
            ),
        ),
        (
            "crawler-ia",
            _("Crawler IA"),
            _(
                "Bot come GPTBot, ClaudeBot, PerplexityBot, Google-Extended che indicizzano per modelli."
            ),
        ),
        (
            "robots-txt",
            "robots.txt",
            _(
                "Policy di accesso crawler; bozza Centropic apre i bot IA utili senza spezzare le regole esistenti."
            ),
        ),
        (
            "geo-token",
            "GEO token",
            _(
                "Unità di credito prodotto (1 token = €0,10). Consumata da analisi e job measured."
            ),
        ),
        (
            "hold",
            "Hold",
            _(
                "Prenotazione temporanea di credito prima di un job; rilasciata o convertita a debito a fine run."
            ),
        ),
        (
            "re-scan",
            "Re-scan",
            _("Nuova analisi dello stesso sito, manuale o schedulata (Plus)."),
        ),
        (
            "white-label",
            "White-label",
            _(
                "Report esportabile con brand agenzia (logo/colori) per clienti finali."
            ),
        ),
        (
            "api-key",
            "API key (gp_…)",
            _("Chiave Bearer per /api/v1 (analyze, sites, edge). Solo Business."),
        ),
        (
            "engine-breakdown",
            "Engine breakdown",
            _(
                "Vista per motore (ChatGPT, Gemini*, Claude, Perplexity, Grok, Azure*) dello Share of Voice."
            ),
        ),
        (
            "pagine-critiche",
            _("Pagine critiche"),
            _(
                "URL del crawl con gap gravi che trascinano score o citabilità."
            ),
        ),
        (
            "before-after",
            "before-after.md",
            _("Documento pack che confronta due run successive dopo fix."),
        ),
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
    """Structured content for /guida and /dashboard/guida (locale-aware)."""
    return {
        "title": _("Guida completa Centropic"),
        "lede": _(
            "Tutto il prodotto in un’unica pagina: analisi AIO/GEO, moduli diagnostici, "
            "pack, Edge Signals, CMS, token, API e glossario."
        ),
        "updated": _("4 agosto 2026"),
        "toc": [
            {"id": "introduzione", "label": _("Introduzione")},
            {"id": "servizi", "label": _("Servizi")},
            {"id": "analisi", "label": _("Analisi e moduli")},
            {"id": "dopo-analisi", "label": _("Dopo l’analisi")},
            {"id": "pack", "label": _("Pack e file")},
            {"id": "edge-cms", "label": _("Edge e CMS")},
            {"id": "piani", "label": _("Piani e token")},
            {"id": "glossario", "label": _("Glossario")},
        ],
        "services": [
            {
                "id": "svc-dashboard",
                "title": _("Dashboard"),
                "image": GUIDE_IMAGES["dashboard"],
                "summary": _(
                    "Workspace unico: ultima analisi, score, findings, SoV e azioni."
                ),
                "bullets": [
                    _("Avvia o ripeti l’analisi sull’URL del sito"),
                    _("Vedi Indice DDD→AAA, score AIO/GEO e Share of Voice"),
                    _("Accedi a pack, Edge Signals, storico e crediti"),
                ],
            },
            {
                "id": "svc-analisi",
                "title": _("Analisi AIO / GEO"),
                "image": GUIDE_IMAGES["analisi"],
                "summary": _(
                    "Probe HTTP + parsing HTML sul dominio: misurato ciò che è osservabile."
                ),
                "bullets": [
                    _("AIO = AI-Driven Visibility (quanto i modelli “vedono” il brand)"),
                    _(
                        "GEO = Generative Engine Optimization (citabilità nelle risposte generate)"
                    ),
                    _("Indice lettera DDD→AAA sintetizza la qualità complessiva"),
                ],
            },
            {
                "id": "svc-findings",
                "title": _("Findings e pagine critiche"),
                "image": GUIDE_IMAGES["findings"],
                "summary": _(
                    "Gap prioritizzati: critical, warn, ok — con azioni concrete."
                ),
                "bullets": [
                    _("Chiudi prima i critical (es. bot IA bloccati in robots)"),
                    _("Usa fix-this-week.md come checklist operativa"),
                    _("Le pagine critiche evidenziano URL con gap gravi"),
                ],
            },
            {
                "id": "svc-pack",
                "title": _("Pack ottimizzazione"),
                "image": GUIDE_IMAGES["pack"],
                "summary": _(
                    "Artifact pronti: llms.txt, JSON-LD, FAQ, meta, robots, before/after."
                ),
                "bullets": [
                    _("Copia dai pannelli o scarica lo ZIP"),
                    _("Su Plus puoi inviare il pack via email"),
                    _(
                        "La pubblicazione sul sito resta a tuo carico (o via Edge/CMS)"
                    ),
                ],
            },
            {
                "id": "svc-edge",
                "title": "Edge Signals",
                "image": GUIDE_IMAGES["edge"],
                "summary": _(
                    "Hosting dinamico degli artifact su centropic.ai/e/<token>/…"
                ),
                "bullets": [
                    _("Free: llms.txt + signals.json"),
                    _("Plus: robots live, organization.jsonld, Worker/Vercel/embed"),
                    _(
                        "Si aggiorna a ogni re-scan e quando cambia la lista crawler IA"
                    ),
                ],
            },
            {
                "id": "svc-cms",
                "title": _("CMS Connector universale"),
                "image": GUIDE_IMAGES["cms"],
                "summary": _(
                    "Un ZIP per WordPress, Drupal, Shopify, PHP, Netlify, Cloudflare, Vercel."
                ),
                "bullets": [
                    _("Attiva Edge, poi scarica il connector dalla dashboard"),
                    _("Un solo adapter sul tuo host: proxy verso Edge"),
                    "API: GET /api/v1/sites/<id>/edge",
                ],
            },
            {
                "id": "svc-sov",
                "title": _("Share of Voice"),
                "image": GUIDE_IMAGES["sov"],
                "summary": _(
                    "Proxy (stimato) su tutti i piani; measured su Plus/Business con citation monitor."
                ),
                "bullets": [
                    _("Stimato: euristiche su segnali del sito"),
                    _("Misurato: prompt bank → menzioni brand nelle risposte LLM"),
                    _(
                        "Gemini e Azure AI restano proxy onesti (non Overview/Copilot nativi)"
                    ),
                ],
            },
            {
                "id": "svc-geo",
                "title": "GEO Suite",
                "image": GUIDE_IMAGES["geo_suite"],
                "summary": _(
                    "Moduli: entity graph, citability, schema, publish verify, llms lint, locales."
                ),
                "bullets": [
                    _("Entity: Organization, sameAs, contatti"),
                    _("Publish verify: controlla se gli artifact sono live"),
                    _("Locales: hreflang e coerenza mercati"),
                ],
            },
            {
                "id": "svc-comp",
                "title": _("Competitor snapshot"),
                "image": GUIDE_IMAGES["competitors"],
                "summary": _(
                    "Confronto rapido AIO/GEO/rating sui competitor (Plus)."
                ),
                "bullets": [
                    _("Stesse metriche del tuo sito"),
                    _("Utile per priorità relative, non ranking assoluto"),
                ],
            },
            {
                "id": "svc-storico",
                "title": _("Storico e re-scan"),
                "image": GUIDE_IMAGES["storico"],
                "summary": _(
                    "Cronologia run, trend e schedulazione automatica (Plus)."
                ),
                "bullets": [
                    _("before-after.md confronta due analisi"),
                    _("Imposta frequenza e orario UTC in Impostazioni"),
                    _("Storico esteso sul piano Plus"),
                ],
            },
            {
                "id": "svc-tokens",
                "title": _("Token GEO e crediti"),
                "image": GUIDE_IMAGES["tokens"],
                "summary": _(
                    "Le analisi e il SoV measured consumano token; i pack ricaricano il saldo."
                ),
                "bullets": [
                    _("1 GEO token = €0,10 (ledger in centesimi)"),
                    _("Pack €10→100, €20→200, €50→600 (bonus)"),
                    _("Plus €14,99/mese include 100 token per ciclo pagato"),
                ],
            },
            {
                "id": "svc-api",
                "title": _("API e white-label"),
                "image": GUIDE_IMAGES["api"],
                "summary": _(
                    "Automazione agenzia: API key, analyze, sites, edge; report white-label."
                ),
                "bullets": [
                    _("Bearer gp_… su /api/v1/*"),
                    _("Export report MD/HTML con brand agenzia"),
                    _("Riservato al piano Business"),
                ],
            },
        ],
        "analyses": [
            {
                "title": _("Crawl e probe"),
                "body": _(
                    "Centropic richiede title, meta, JSON-LD, FAQ, robots, llms.txt, sitemap, "
                    "ai.txt, humans.txt e pagine del sito. Free: tetto pagine; Plus: crawl intero "
                    "(con tetto operativo di piattaforma)."
                ),
            },
            {
                "title": "Engine breakdown",
                "body": _(
                    "Vista per ChatGPT, Gemini (proxy AI Overview), Claude, Perplexity, Grok e "
                    "Azure AI. Di default è Stimato; con SoV measured gli engine disponibili "
                    "passano a Misurato."
                ),
            },
            {
                "title": "Entity graph",
                "body": _(
                    "Valuta coerenza Organization / brand, sameAs, contatti e segnali entity "
                    "riutilizzabili da crawler e modelli."
                ),
            },
            {
                "title": "Citability",
                "body": _(
                    "Quanto il copy è citabile: claim chiari, definizioni, fatti verificabili, "
                    "meno ambiguità sul “chi siete / cosa fate”."
                ),
            },
            {
                "title": "Schema quality",
                "body": _(
                    "Qualità e completezza JSON-LD (Organization, WebSite, FAQPage, "
                    "SoftwareApplication, Article dove rilevante)."
                ),
            },
            {
                "title": "Publish verify",
                "body": _(
                    "Verifica se llms.txt, robots e schema pubblicati sul dominio corrispondono "
                    "alle bozze del pack / Edge."
                ),
            },
            {
                "title": "llms lint",
                "body": _(
                    "Controlla presenza e qualità di /llms.txt: brand, topic, URL assoluti, "
                    "preferred citation."
                ),
            },
            {
                "title": "Locales",
                "body": _(
                    "Segnali hreflang / mercati: coerenza linguistica e copertura internazionale "
                    "per answer engine multi-lingua."
                ),
            },
            {
                "title": _("SoV measured"),
                "body": _(
                    "Solo Plus: citation monitor con prompt bank. Conta menzioni brand/dominio "
                    "nelle risposte — campione probe, non garanzia di ranking nelle UI consumer."
                ),
            },
        ],
        "workflow": [
            {
                "title": _("Indice DDD→AAA"),
                "body": _(
                    "Leggi la lettera: DDD è critico, AAA è top. Mira a salire di almeno un grado tra un re-scan e l’altro."
                ),
            },
            {
                "title": _("Score AIO / GEO"),
                "body": _(
                    "Sotto 60 = intervento prioritario. AIO e GEO vanno letti insieme al SoV, non isolati."
                ),
            },
            {
                "title": "Findings",
                "body": _(
                    "Chiudi critical e warn; usa fix-this-week.md. Poi ripubblica e verifica."
                ),
            },
            {
                "title": _("Pubblica llms.txt"),
                "body": _(
                    "Root del sito: https://tuodominio/llms.txt — oppure Edge + CMS connector."
                ),
            },
            {
                "title": "JSON-LD + FAQ + meta",
                "body": _(
                    "Incolla nel <head> delle pagine chiave (o lascia Edge servire organization.jsonld)."
                ),
            },
            {
                "title": "robots.txt",
                "body": _(
                    "Unisci la bozza al file esistente; lascia aperti i bot IA utili (GPTBot, ClaudeBot, …)."
                ),
            },
            {
                "title": "Re-scan",
                "body": _(
                    "Su Plus imposta frequenza/orario UTC e confronta before/after.md."
                ),
            },
        ],
        "pack_files": [
            {"file": "llms.txt", "where": _("root del sito")},
            {
                "file": "organization.jsonld.html",
                "where": _("<head> o Edge /.well-known/"),
            },
            {"file": "faq.jsonld.html", "where": "<head>"},
            {"file": "meta-pack.html", "where": "<head>"},
            {"file": "robots.txt", "where": _("root del sito")},
            {
                "file": "fix-this-week.md",
                "where": _("checklist operativa interna"),
            },
            {"file": "before-after.md", "where": _("confronto tra run")},
            {
                "file": "signals.json",
                "where": _("Edge /geopulse/signals.json via CMS"),
            },
        ],
        "plans": [
            {
                "name": "Free",
                "points": [
                    _(
                        "1 sito, crawl pagine limitate, 2 analisi su nuovi siti (ri-analisi stesso URL ok, consuma token)"
                    ),
                    _("Score, findings, pack ZIP, Edge base (llms + signals)"),
                    _("SoV stimato (proxy)"),
                ],
            },
            {
                "name": "Plus · €14,99",
                "points": [
                    _(
                        "Fino a 5 siti, crawl fino a 120 pagine (Deep 500), competitor, storico esteso"
                    ),
                    _("SoV measured, prompt bank, re-scan, alert, Edge completo"),
                    _("100 token per ciclo di fatturazione"),
                ],
            },
            {
                "name": "Business · €49,99",
                "points": [
                    _("Tutto Plus + fino a 50 siti e 400 token/mese"),
                    _("API /api/v1 e white-label MD/HTML con brand agenzia"),
                    _("Profilo consigliato per portfolio clienti"),
                ],
            },
        ],
        "glossary": _glossary_entries(),
        "deep_links": [
            {
                "href": "/metodologia",
                "label": _("Metodologia (Misurato vs Stimato)"),
            },
            {"href": "/guide/llms-txt", "label": _("Guida llms.txt")},
            {
                "href": "/guide/schema-ai",
                "label": _("Schema.org per answer engine"),
            },
            {
                "href": "/guide/score-vs-sov",
                "label": _("Score AIO/GEO vs SoV"),
            },
            {"href": "/faq", "label": "FAQ"},
            {"href": "/prodotto", "label": _("Prodotto")},
            {"href": "/prezzi", "label": _("Piani e prezzi")},
            {"href": "/guida", "label": _("Guida completa")},
            {"href": "/esempio-report", "label": _("Esempio report")},
            {"href": "/agenzie", "label": _("Per agenzie")},
            {"href": "/status", "label": "Status"},
        ],
    }
