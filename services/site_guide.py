"""Complete Centropic site guide + glossary (single source of truth)."""

from __future__ import annotations

from typing import Any

from flask_babel import gettext as _


def _glossary_entries() -> list[dict[str, str]]:
    raw = [
        (
            "cvi",
            _("CVI (Centropic Visibility Index)"),
            _(
                "Metrica proprietaria Centropic: indice 0–100 con lettera DD→AA che sintetizza AIO+GEO "
                "(con penalità findings). In Panoramica il voto sta nel marchio; il punteggio numerico sta a destra. "
                "È lo standard da confrontare tra brand — non Domain Authority di terzi."
            ),
        ),
        (
            "aio",
            "AIO",
            _(
                "AI-Driven Visibility: componente del CVI — quanto brand e sito sono comprensibili/visibili a modelli e crawler IA. Non significa All-in-One."
            ),
        ),
        (
            "geo",
            "GEO",
            _(
                "Generative Engine Optimization: componente del CVI — ottimizzazione per essere citati nelle risposte generate. Non significa GIS."
            ),
        ),
        (
            "sov",
            _("Citation share (SoV)"),
            _(
                "Campione di menzioni del brand nelle risposte generative (stocastiche), non Share of Voice pubblicitaria. "
                "Proxy = stimato dalla struttura; Measured = citation monitor (Plus)."
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
            _("CVI · scala DD→AA"),
            _(
                "Lettera del Centropic Visibility Index, da critica (DD) a eccellente (AA). Alias storico: “Indice”."
            ),
        ),
        (
            "indice-criticita",
            _("Indice di criticità"),
            _(
                "Score 0–100 dalla mix dei finding del run: (critici × 100 + warning × 40) / totale. "
                "In Panoramica sta sotto Distribuzione AIO, stessa colonna Crawl."
            ),
        ),
        (
            "workspace",
            _("Workspace"),
            _(
                "Le cinque pagine del prodotto: Panoramica, Benchmark, Prompt, Trend, Guida. "
                "Account e impostazioni restano nel menu avatar."
            ),
        ),
        (
            "finding",
            _("Finding"),
            _(
                "Singolo gap o conferma (critical / warn / ok) con contesto e priorità."
            ),
        ),
        (
            "pack",
            _("Pack"),
            _(
                "Insieme di artifact generati dall’analisi. Il file centropic-fix.html include il logo originale in testa, "
                "score, finding e snippet (llms, schema, meta, robots, checklist)."
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
            _("Grafo entità"),
            _(
                "Rete di segnali entity (nome, sameAs, contatti) che disambiguano il brand."
            ),
        ),
        (
            "citability",
            _("Citabilità"),
            _(
                "Quanto il contenuto è facilmente citabile da un modello (chiarezza, fatti, struttura)."
            ),
        ),
        (
            "schema-quality",
            _("Qualità schema"),
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
            _("Quota operativa"),
            _(
                "Credito incluso nel piano (e nei pacchetti extra) che copre analisi e job measured. In dashboard compare come copertura residua in euro — non serve calcolare “token” API."
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
            _("Re-scan"),
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
            "API key (ct_…)",
            _(
                "Chiave Bearer ct_ per /api/v1 (analyze, sites, edge). "
                "Le chiavi gp_ legacy restano accettate. Solo Business."
            ),
        ),
        (
            "engine-breakdown",
            _("Ripartizione motori"),
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
            "Come leggere il workspace: le cinque pagine, il CVI sul marchio, "
            "i grafici AIO/GEO, l’indice di criticità, i pack e l’Edge."
        ),
        "updated": _("21 agosto 2026"),
        "toc": [
            {"id": "introduzione", "label": _("Introduzione")},
            {"id": "workspace", "label": _("Workspace")},
            {"id": "servizi", "label": _("Servizi")},
            {"id": "analisi", "label": _("Analisi e moduli")},
            {"id": "dopo-analisi", "label": _("Dopo l’analisi")},
            {"id": "pack", "label": _("Pack e file")},
            {"id": "edge-cms", "label": _("Edge e CMS")},
            {"id": "piani", "label": _("Piani: domini, re-scan, API")},
            {"id": "glossario", "label": _("Glossario")},
        ],
        "workspace": {
            "title": _("Le cinque pagine"),
            "lede": _(
                "Il workspace ha una sola barra in alto. Cinque destinazioni, stesso dominio attivo. "
                "Account e impostazioni restano nel menu avatar."
            ),
            "pages": [
                {
                    "title": _("Panoramica"),
                    "body": _(
                        "Dominio e CVI in testa. Sotto: sette KPI, Composizione e Motori alla stessa altezza, "
                        "poi Suite e Mix, poi Crawl AIO con Distribuzione AIO e Indice di criticità "
                        "nella stessa colonna, ledger pagine a destra. In coda: storico run e findings."
                    ),
                },
                {
                    "title": _("Benchmark"),
                    "body": _(
                        "Confronta il sito attivo con i rivali su AIO, GEO, SoV e motori. "
                        "Usa uno snapshot già misurato, non un grafico inventato."
                    ),
                },
                {
                    "title": _("Prompt"),
                    "body": _(
                        "Le query usate per misurare il SoV e i finding aperti. "
                        "Qui si vede cosa è stato chiesto ai motori e il pack da applicare."
                    ),
                },
                {
                    "title": _("Trend"),
                    "body": _(
                        "Storico delle run sul dominio attivo. Due grafici affiancati: AIO/GEO nel tempo "
                        "e CVI per run, con le date sotto ogni punto. Serve almeno due analisi."
                    ),
                },
                {
                    "title": _("Guida"),
                    "body": _(
                        "Questo manuale, dentro il workspace. Stesso contenuto della pagina pubblica /guida."
                    ),
                },
            ],
        },
        "services": [
            {
                "id": "svc-dashboard",
                "title": _("Workspace"),
                "image": GUIDE_IMAGES["dashboard"],
                "summary": _(
                    "Cinque pagine, un dominio attivo, grafici dallo stesso run."
                ),
                "bullets": [
                    _("Panoramica: CVI sul marchio (voto DD–AA nel C, punteggio a destra), KPI e grafici"),
                    _("Benchmark, Prompt e Trend sul dominio selezionato dai chip"),
                    _("Account e impostazioni nel menu avatar — non in una sesta pill"),
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
                    _("CVI (Centropic Visibility Index): lettera DD→AA sul compositario AIO+GEO"),
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
                    _(
                        "Indice di criticità: (critici × 100 + warning × 40) / totale, "
                        "sotto Distribuzione AIO nello stack Crawl"
                    ),
                    _("Le pagine critiche evidenziano URL con gap gravi"),
                ],
            },
            {
                "id": "svc-pack",
                "title": _("Pack ottimizzazione"),
                "image": GUIDE_IMAGES["pack"],
                "summary": _(
                    "Pack HTML con logo originale, score, finding e snippet da pubblicare."
                ),
                "bullets": [
                    _("Scarica centropic-fix.html: si apre offline, logo in testa"),
                    _("Su Plus puoi inviare il pack via email"),
                    _(
                        "La pubblicazione sul sito resta a tuo carico (o via Edge/CMS)"
                    ),
                ],
            },
            {
                "id": "svc-edge",
                "title": _("Edge Signals"),
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
                    _("API: GET /api/v1/sites/<id>/edge"),
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
                "title": _("GEO Suite"),
                "image": GUIDE_IMAGES["geo_suite"],
                "summary": _(
                    "Moduli: grafo entità, citabilità, schema, publish verify, llms lint, mercati."
                ),
                "bullets": [
                    _("Entity: Organization, sameAs, contatti"),
                    _("Publish verify: controlla se gli artifact sono live"),
                    _("Mercati e lingue: hreflang e coerenza"),
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
                "title": _("Trend e re-scan"),
                "image": GUIDE_IMAGES["storico"],
                "summary": _(
                    "Serie temporale sul dominio attivo: AIO/GEO e CVI, con le date sotto ogni punto."
                ),
                "bullets": [
                    _("Due grafici affiancati: AIO/GEO e CVI per run"),
                    _("Imposta frequenza e orario UTC in Impostazioni"),
                    _("before-after.md confronta due analisi successive"),
                ],
            },
            {
                "id": "svc-tokens",
                "title": _("Quota operativa e copertura"),
                "image": GUIDE_IMAGES["tokens"],
                "summary": _(
                    "Ogni piano include una quota operativa mensile. I pacchetti extra ampliano la copertura senza cambiare piano."
                ),
                "bullets": [
                    _("Scegli il piano per domini, frequenza di re-scan e API/white-label"),
                    _("Pacchetti extra in euro per picchi di ri-analisi o clienti"),
                    _("La quota del rinnovo mensile è inclusa nel canone Plus/Business"),
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
                    _("Bearer ct_… su /api/v1/* (gp_… legacy accettato)"),
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
                "title": _("Ripartizione motori"),
                "body": _(
                    "Vista per ChatGPT, Gemini (API), Claude, Perplexity, Grok e "
                    "Azure AI. Di default è Stimato; con SoV measured gli engine disponibili "
                    "passano a Misurato."
                ),
            },
            {
                "title": _("Grafo entità"),
                "body": _(
                    "Valuta coerenza Organization / brand, sameAs, contatti e segnali entity "
                    "riutilizzabili da crawler e modelli."
                ),
            },
            {
                "title": _("Citabilità"),
                "body": _(
                    "Quanto il copy è citabile: claim chiari, definizioni, fatti verificabili, "
                    "meno ambiguità sul “chi siete / cosa fate”."
                ),
            },
            {
                "title": _("Qualità schema"),
                "body": _(
                    "Qualità e completezza JSON-LD (Organization, WebSite, FAQPage, "
                    "SoftwareApplication, Article dove rilevante)."
                ),
            },
            {
                "title": _("Publish verify"),
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
                "title": _("Mercati e lingue"),
                "body": _(
                    "Segnali hreflang / mercati: coerenza linguistica e copertura internazionale "
                    "per answer engine multi-lingua."
                ),
            },
            {
                "title": _("Citation share measured"),
                "body": _(
                    "Solo Plus: citation monitor con prompt bank. Conta menzioni brand/dominio "
                    "nelle risposte generative (stocastiche) — non Share of Voice pubblicitaria, "
                    "non garanzia di ranking nelle UI consumer."
                ),
            },
        ],
        "workflow": [
            {
                "title": _("CVI (Centropic Visibility Index)"),
                "body": _(
                    "Leggi lettera e score: DD è critico, AA è top. Il voto sta nel marchio, "
                    "il numero a destra. Mira a salire di almeno un grado CVI tra un re-scan e l’altro."
                ),
            },
            {
                "title": _("Score AIO / GEO"),
                "body": _(
                    "Componenti del CVI. Sotto 60 = intervento prioritario. Poi campiona la citation share — non isolare i numeri."
                ),
            },
            {
                "title": _("Findings"),
                "body": _(
                    "Chiudi critical e warn; usa l’indice di criticità e il pack. Poi ripubblica e verifica."
                ),
            },
            {
                "title": _("Pubblica llms.txt"),
                "body": _(
                    "Root del sito: %(path)s — oppure Edge + CMS connector."
                )
                % {"path": _("https://tuodominio/llms.txt")},
            },
            {
                "title": _("JSON-LD + FAQ + meta"),
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
                "title": _("Re-scan"),
                "body": _(
                    "Su Plus imposta frequenza/orario UTC e confronta before/after.md."
                ),
            },
        ],
        "pack_files": [
            {
                "file": "centropic-fix.html",
                "where": _(
                    "unico deliverable: logo originale in testa; apri e copia head / llms.txt / robots sul sito"
                ),
            },
            {
                "file": "signals.json",
                "where": _("Edge /geopulse/signals.json via CMS (opzionale)"),
            },
        ],
        "plans": [
            {
                "name": _("Free"),
                "points": [
                    _(
                        "1 dominio monitorato, crawl limitato, analisi iniziali incluse"
                    ),
                    _("Score, findings, pack HTML unico, Edge base (llms + signals)"),
                    _("Re-scan: manuale · SoV stimato (proxy)"),
                ],
            },
            {
                "name": _("Plus · €19,99 Tasse escluse"),
                "points": [
                    _(
                        "Fino a 5 domini, crawl fino a 120 pagine (Deep 500), competitor, storico esteso"
                    ),
                    _("Re-scan giornaliero/settimanale, SoV measured, prompt bank, alert, Edge completo"),
                    _("API / white-label: non inclusi"),
                ],
            },
            {
                "name": _("Business · €89,99 Tasse escluse"),
                "points": [
                    _("Tutto Plus + fino a 50 domini / clienti"),
                    _("API /api/v1 e white-label MD/HTML con brand agenzia"),
                    _("Profilo consigliato per portfolio multi-cliente"),
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
                "label": _("CVI · score · citation share"),
            },
            {"href": "/faq", "label": _("FAQ")},
            {"href": "/prodotto", "label": _("Prodotto")},
            {"href": "/prezzi", "label": _("Piani e prezzi")},
            {"href": "/guida", "label": _("Guida completa")},
            {"href": "/esempio-report", "label": _("Esempio report")},
            {"href": "/status", "label": _("Stato")},
        ],
    }
