#!/usr/bin/env python3
"""Upsert dashboard titles, URL placeholders, and updated guide strings; compile .mo."""

from __future__ import annotations

from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]

# Italian msgid (source) → native msgstr.
EN = {
    "Panoramica": "Overview",
    "Benchmark": "Benchmark",
    "Prompt": "Prompt",
    "Trend": "Trend",
    "Dominio attivo": "Active domain",
    "Nuovo dominio": "New domain",
    "Distribuzione AIO": "AIO distribution",
    "Indice di criticità": "Criticality index",
    "Composizione": "Composition",
    "Motori": "Engines",
    "Ledger": "Ledger",
    "Aperti": "Open",
    "Pagine": "Pages",
    "Findings e pack": "Findings and pack",
    "Cerca o incolla URL": "Search or paste URL",
    "Seleziona dominio": "Select domain",
    "Audit": "Audit",
    "Mix": "Mix",
    "Campo": "Field",
    "Andamento AIO e GEO": "AIO and GEO trend",
    "AIO / GEO per data": "AIO / GEO by date",
    "Vai alla Panoramica": "Go to Overview",
    "Findings aperti e deliverable da applicare.": "Open findings and deliverables to apply.",
    "aperti sul run analizzato": "open on the analyzed run",
    "Pagine per fascia AIO": "Pages by AIO band",
    "Nessun breakdown disponibile.": "No breakdown available.",
    "Nessuna pagina con score AIO.": "No pages with an AIO score.",
    "Nessuna criticità aperta.": "No open issues.",
    "Nessuna pagina in crawl.": "No pages in the crawl.",
    "Nessuna analisi ancora": "No analyses yet",
    "Competitor (max 3)": "Competitors (max 3)",
    "Aggiungi competitor": "Add competitor",
    "Deep crawl": "Deep crawl",
    "Saldo token": "Token balance",
    "Metriche": "Metrics",
    "Metriche primarie": "Primary metrics",
    "Critici": "Critical",
    "Warn": "Warn",
    "Italia": "Italy",
    "https://tuosito.com": "https://yoursite.com",
    "https://iltuosito.it": "https://yoursite.com",
    "https://rivale.com": "https://rival.com",
    "https://rivale1.com": "https://rival1.com",
    "https://rivale2.com": "https://rival2.com",
    "https://tuodominio/llms.txt": "https://yourdomain.com/llms.txt",
    "21 agosto 2026": "August 21, 2026",
    "23 agosto 2026": "August 23, 2026",
    "Tasse escluse": "excl. tax",
    "Analizza gratis": "Analyze for free",
    "Come leggere il workspace: le cinque pagine, il CVI sul marchio, i grafici AIO/GEO, l’indice di criticità, i pack e l’Edge.": (
        "How to read the workspace: the five pages, CVI on the mark, AIO/GEO charts, "
        "the criticality index, packs, and Edge."
    ),
    "Le cinque pagine": "The five pages",
    "Il workspace ha una sola barra in alto. Cinque destinazioni, stesso dominio attivo. Account e impostazioni restano nel menu avatar.": (
        "The workspace has a single top bar. Five destinations, same active domain. "
        "Account and settings stay in the avatar menu."
    ),
    "Dominio e CVI in testa. Sotto: sette KPI, Composizione e Motori alla stessa altezza, poi Suite e Mix, poi Crawl AIO con Distribuzione AIO e Indice di criticità nella stessa colonna, ledger pagine a destra. In coda: storico run e findings.": (
        "Domain and CVI at the top. Below: seven KPIs, Composition and Engines at the same height, "
        "then Suite and Mix, then AIO Crawl with AIO distribution and Criticality index "
        "in the same column, pages ledger on the right. At the bottom: run history and findings."
    ),
    "Confronta il sito attivo con i rivali su AIO, GEO, SoV e motori. Usa uno snapshot già misurato, non un grafico inventato.": (
        "Compare the active site with rivals on AIO, GEO, SoV, and engines. "
        "Uses a measured snapshot, not an invented chart."
    ),
    "Le query usate per misurare il SoV e i finding aperti. Qui si vede cosa è stato chiesto ai motori e il pack da applicare.": (
        "The queries used to measure SoV and the open findings. "
        "See what was asked of the engines and the pack to apply."
    ),
    "Storico delle run sul dominio attivo. Due grafici affiancati: AIO/GEO nel tempo e CVI per run, con le date sotto ogni punto. Serve almeno due analisi.": (
        "Run history on the active domain. Two side-by-side charts: AIO/GEO over time "
        "and CVI per run, with dates under each point. Needs at least two analyses."
    ),
    "Questo manuale, dentro il workspace. Stesso contenuto della pagina pubblica /guida.": (
        "This manual, inside the workspace. Same content as the public /guida page."
    ),
    "Cinque pagine, un dominio attivo, grafici dallo stesso run.": (
        "Five pages, one active domain, charts from the same run."
    ),
    "Panoramica: CVI sul marchio (voto DD–AA nel C, punteggio a destra), KPI e grafici": (
        "Overview: CVI on the mark (DD–AA grade inside the C, score on the right), KPIs and charts"
    ),
    "Benchmark, Prompt e Trend sul dominio selezionato dai chip": (
        "Benchmark, Prompt, and Trend on the domain selected from the chips"
    ),
    "Account e impostazioni nel menu avatar — non in una sesta pill": (
        "Account and settings in the avatar menu — not a sixth pill"
    ),
    "Indice di criticità: (critici × 100 + warning × 40) / totale, sotto Distribuzione AIO nello stack Crawl": (
        "Criticality index: (critical × 100 + warning × 40) / total, under AIO distribution in the Crawl stack"
    ),
    "Pack HTML con logo originale, score, finding e snippet da pubblicare.": (
        "HTML pack with the original logo, score, findings, and snippets to publish."
    ),
    "Scarica centropic-fix.html: si apre offline, logo in testa": (
        "Download centropic-fix.html: opens offline, original logo at the top"
    ),
    "Moduli: grafo entità, citabilità, schema, publish verify, llms lint, mercati.": (
        "Modules: entity graph, citability, schema, publish verify, llms lint, locales."
    ),
    "Mercati e lingue: hreflang e coerenza": "Locales: hreflang and consistency",
    "Trend e re-scan": "Trend and re-scan",
    "Serie temporale sul dominio attivo: AIO/GEO e CVI, con le date sotto ogni punto.": (
        "Time series on the active domain: AIO/GEO and CVI, with dates under each point."
    ),
    "Due grafici affiancati: AIO/GEO e CVI per run": (
        "Two side-by-side charts: AIO/GEO and CVI per run"
    ),
    "Ripartizione motori": "Engine breakdown",
    "Grafo entità": "Entity graph",
    "Citabilità": "Citability",
    "Qualità schema": "Schema quality",
    "Mercati e lingue": "Locales",
    "Leggi lettera e score: DD è critico, AA è top. Il voto sta nel marchio, il numero a destra. Mira a salire di almeno un grado CVI tra un re-scan e l’altro.": (
        "Read the letter and score: DD is critical, AA is top. The grade sits in the mark, "
        "the number on the right. Aim to climb at least one CVI grade between re-scans."
    ),
    "Chiudi critical e warn; usa l’indice di criticità e il pack. Poi ripubblica e verifica.": (
        "Close critical and warn items; use the criticality index and the pack. Then republish and verify."
    ),
    "Root del sito: %(path)s — oppure Edge + CMS connector.": (
        "Site root: %(path)s — or Edge + CMS connector."
    ),
    "unico deliverable: logo originale in testa; apri e copia head / llms.txt / robots sul sito": (
        "single deliverable: original logo at the top; open and copy head / llms.txt / robots onto the site"
    ),
    "Plus · €19,99 Tasse escluse": "Plus · €19.99 excl. tax",
    "Business · €89,99 Tasse escluse": "Business · €89.99 excl. tax",
    "Metrica proprietaria Centropic: indice 0–100 con lettera DD→AA che sintetizza AIO+GEO (con penalità findings). In Panoramica il voto sta nel marchio; il punteggio numerico sta a destra. È lo standard da confrontare tra brand — non Domain Authority di terzi.": (
        "Centropic’s proprietary metric: a 0–100 index with a DD→AA letter that synthesizes AIO+GEO "
        "(with findings penalties). On Overview the grade sits in the mark; the numeric score sits to the right. "
        "It is the standard to compare brands — not third-party Domain Authority."
    ),
    "Score 0–100 dalla mix dei finding del run: (critici × 100 + warning × 40) / totale. In Panoramica sta sotto Distribuzione AIO, stessa colonna Crawl.": (
        "0–100 score from the run’s finding mix: (critical × 100 + warning × 40) / total. "
        "On Overview it sits under AIO distribution, same Crawl column."
    ),
    "Le cinque pagine del prodotto: Panoramica, Benchmark, Prompt, Trend, Guida. Account e impostazioni restano nel menu avatar.": (
        "The product’s five pages: Overview, Benchmark, Prompt, Trend, Guide. "
        "Account and settings stay in the avatar menu."
    ),
    "Insieme di artifact generati dall’analisi. Il file centropic-fix.html include il logo originale in testa, score, finding e snippet (llms, schema, meta, robots, checklist).": (
        "Set of artifacts from the analysis. centropic-fix.html includes the original logo at the top, "
        "score, findings, and snippets (llms, schema, meta, robots, checklist)."
    ),
    "Il workspace ha cinque pagine: Panoramica, Benchmark, Prompt, Trend, Guida.": (
        "The workspace has five pages: Overview, Benchmark, Prompt, Trend, Guide."
    ),
    "Workspace: CVI sul marchio, grafici AIO/GEO e pack in cinque pagine.": (
        "Workspace: CVI on the mark, AIO/GEO charts, and packs across five pages."
    ),
    "Stato": "Status",
    "JSON-LD + FAQ + meta": "JSON-LD + FAQ + meta",
    "API: GET /api/v1/sites/<id>/edge": "API: GET /api/v1/sites/<id>/edge",
    "Finding": "Finding",
    "Pack": "Pack",
    "Quota operativa": "Operating quota",
    "Cosa misuriamo — e cosa no": "What we measure — and what we don't",
    "Tre richieste frequenti in discovery restano fuori dal prodotto. Non per roadmap vuota: perché non le possiamo misurare in modo onesto, o perché brucerebbero la quota operativa senza rendere il sito più citabile.": (
        "Three questions that come up often in sales conversations aren't in the product. "
        "That's not a hole in the roadmap: we can't measure them honestly, "
        "or they'd burn your monthly quota without making the site more citable."
    ),
    "Attribution e ROI dalle citazioni LLM": "Attribution and ROI from LLM citations",
    "ChatGPT, Claude, Perplexity e Copilot non espongono impression, click o CTR. Un “ricavo generato dalla visibilità AI” sarebbe una correlazione inventata. Centropic misura le menzioni sul prompt bank (SoV Misurato) e, su Plus, può collegare Search Console come baseline di Search — non come traffico AI. Quando avremo sessioni con referrer AI dichiarati dal tuo analytics, le metteremo in Trend con l’etichetta Stimato.": (
        "ChatGPT, Claude, Perplexity, and Copilot do not expose impressions, clicks, or CTR. "
        "A “revenue from AI visibility” number would be a made-up correlation. "
        "Centropic measures brand mentions against your prompt bank (Measured SoV) and, on Plus, "
        "can connect Search Console as a Search baseline — not as AI traffic. "
        "When we have sessions with AI referrers reported by your analytics, "
        "we'll put them on Trend and label them Estimated."
    ),
    "Simulazioni agente (buyer persona / funnel d’acquisto)": (
        "Agent simulations (buyer personas and purchase funnels)"
    ),
    "Un journey multi-turno (CTO, procurement) moltiplica le probe LLM: un sim pieno può costare quanto 4–10 analisi Misurate e resta stocastico. Oggi il prompt bank su Plus accetta domande in stile buyer; non lanciamo agenti nel POST analyze perché svuoterebbero la quota mensile senza pubblicare un artifact. Se serve un report journey, è uno SKU a parte, non il default.": (
        "A multi-turn journey (CTO, procurement) multiplies LLM probes: a full simulation can cost "
        "as much as 4–10 Measured analyses and is still stochastic. "
        "The Plus prompt bank already accepts buyer-style questions. "
        "We do not launch agents on POST /analyze — that would empty the monthly quota without publishing an artifact. "
        "If you need a journey report, that is a separate SKU, not the default."
    ),
    "Audit nei dataset di pre-training (Common Crawl, Reddit, “pesi” GPT)": (
        "Pre-training data audits (Common Crawl, Reddit, GPT “weights”)"
    ),
    "Nessun modello chiuso certifica se il brand è nei suoi pesi. Dirlo in dashboard sarebbe un claim commerciale, non una misura. La GEO Suite già legge il tuo sito (grafo entità, sameAs, schema). Una presenza su Wikipedia/Wikidata è un finding utile; “sei nel training di ChatGPT” no. Restiamo su ciò che è osservabile.": (
        "No closed model will certify that your brand is in its weights. "
        "Putting that on a dashboard would be a marketing claim, not a measurement. "
        "The GEO Suite already reads your site (entity graph, sameAs, schema). "
        "A Wikipedia/Wikidata presence is a useful finding; “you are in ChatGPT’s training data” is not. "
        "We stay with what we can observe."
    ),
    "Plus/Business: webhook pack.ready (checksum + URL Edge) così il CMS applica senza copiare i file": (
        "Plus/Business: pack.ready webhook (checksums + Edge URLs) so your CMS can apply the pack without copy-paste"
    ),
    "APPLY.md nello ZIP: evento pack.ready, idempotenza su signals_version": (
        "APPLY.md in the ZIP: pack.ready event, idempotent on signals_version"
    ),
    "GET /sites/<id> e /runs: AIO, GEO, CVI, SoV, criticità, checksum — OpenAPI in /api/v1/openapi.json": (
        "GET /sites/<id> and /runs: AIO, GEO, CVI, SoV, criticality, checksums — OpenAPI at /api/v1/openapi.json"
    ),
    "Webhook analysis.completed + pack.ready (oltre agli alert di regressione)": (
        "analysis.completed and pack.ready webhooks (plus regression alerts)"
    ),
    "Approfondimento su Misurato vs Stimato nella": "Read more about Measured vs Estimated in the",
    "Eventi: analysis.completed, pack.ready (checksum + URL Edge, senza body dei file), analysis.alert (solo regressioni).": (
        "Events: analysis.completed, pack.ready (checksums + Edge URLs, no file bodies), analysis.alert (regressions only)."
    ),
    "Firma HMAC in X-Centropic-Signature. Applica pack.ready una volta per idempotency_key.": (
        "HMAC signature in X-Centropic-Signature. Apply pack.ready once per idempotency_key."
    ),
}

DE = {
    "Panoramica": "Übersicht",
    "Benchmark": "Benchmark",
    "Prompt": "Prompt",
    "Trend": "Trend",
    "Dominio attivo": "Aktive Domain",
    "Nuovo dominio": "Neue Domain",
    "Distribuzione AIO": "AIO-Verteilung",
    "Indice di criticità": "Kritikalitätsindex",
    "Composizione": "Zusammensetzung",
    "Motori": "Engines",
    "Ledger": "Ledger",
    "Aperti": "Offen",
    "Pagine": "Seiten",
    "Findings e pack": "Findings und Pack",
    "Cerca o incolla URL": "URL suchen oder einfügen",
    "Seleziona dominio": "Domain wählen",
    "Audit": "Audit",
    "Mix": "Mix",
    "Campo": "Feld",
    "Andamento AIO e GEO": "AIO- und GEO-Verlauf",
    "AIO / GEO per data": "AIO / GEO nach Datum",
    "Vai alla Panoramica": "Zur Übersicht",
    "Findings aperti e deliverable da applicare.": "Offene Findings und anzuwendende Deliverables.",
    "aperti sul run analizzato": "offen im analysierten Lauf",
    "Pagine per fascia AIO": "Seiten nach AIO-Band",
    "Nessun breakdown disponibile.": "Keine Aufschlüsselung verfügbar.",
    "Nessuna pagina con score AIO.": "Keine Seiten mit AIO-Score.",
    "Nessuna criticità aperta.": "Keine offenen Probleme.",
    "Nessuna pagina in crawl.": "Keine Seiten im Crawl.",
    "Nessuna analisi ancora": "Noch keine Analysen",
    "Competitor (max 3)": "Wettbewerber (max. 3)",
    "Aggiungi competitor": "Wettbewerber hinzufügen",
    "Deep crawl": "Deep Crawl",
    "Saldo token": "Token-Saldo",
    "Metriche": "Kennzahlen",
    "Metriche primarie": "Primäre Kennzahlen",
    "Critici": "Kritisch",
    "Warn": "Warn",
    "Italia": "Italien",
    "https://tuosito.com": "https://deine-seite.de",
    "https://iltuosito.it": "https://deine-seite.de",
    "https://rivale.com": "https://wettbewerber.de",
    "https://rivale1.com": "https://wettbewerber1.de",
    "https://rivale2.com": "https://wettbewerber2.de",
    "https://tuodominio/llms.txt": "https://deine-domain.de/llms.txt",
    "21 agosto 2026": "21. August 2026",
    "Come leggere il workspace: le cinque pagine, il CVI sul marchio, i grafici AIO/GEO, l’indice di criticità, i pack e l’Edge.": (
        "So lesen Sie den Workspace: die fünf Seiten, der CVI auf dem Markenzeichen, "
        "AIO/GEO-Diagramme, der Kritikalitätsindex, Packs und Edge."
    ),
    "Le cinque pagine": "Die fünf Seiten",
    "Il workspace ha una sola barra in alto. Cinque destinazioni, stesso dominio attivo. Account e impostazioni restano nel menu avatar.": (
        "Der Workspace hat eine einzige Leiste oben. Fünf Ziele, dieselbe aktive Domain. "
        "Konto und Einstellungen bleiben im Avatar-Menü."
    ),
    "Dominio e CVI in testa. Sotto: sette KPI, Composizione e Motori alla stessa altezza, poi Suite e Mix, poi Crawl AIO con Distribuzione AIO e Indice di criticità nella stessa colonna, ledger pagine a destra. In coda: storico run e findings.": (
        "Domain und CVI oben. Darunter: sieben KPIs, Zusammensetzung und Engines auf gleicher Höhe, "
        "dann Suite und Mix, dann AIO-Crawl mit AIO-Verteilung und Kritikalitätsindex "
        "in derselben Spalte, Seiten-Ledger rechts. Unten: Laufhistorie und Findings."
    ),
    "Confronta il sito attivo con i rivali su AIO, GEO, SoV e motori. Usa uno snapshot già misurato, non un grafico inventato.": (
        "Vergleicht die aktive Website mit Rivalen nach AIO, GEO, SoV und Engines. "
        "Nutzt einen gemessenen Snapshot, kein erfundenes Diagramm."
    ),
    "Le query usate per misurare il SoV e i finding aperti. Qui si vede cosa è stato chiesto ai motori e il pack da applicare.": (
        "Die Abfragen zur SoV-Messung und die offenen Findings. "
        "Hier sehen Sie, was die Engines gefragt wurden und welches Pack anzuwenden ist."
    ),
    "Storico delle run sul dominio attivo. Due grafici affiancati: AIO/GEO nel tempo e CVI per run, con le date sotto ogni punto. Serve almeno due analisi.": (
        "Laufhistorie der aktiven Domain. Zwei Diagramme nebeneinander: AIO/GEO im Zeitverlauf "
        "und CVI pro Lauf, mit Datum unter jedem Punkt. Mindestens zwei Analysen nötig."
    ),
    "Questo manuale, dentro il workspace. Stesso contenuto della pagina pubblica /guida.": (
        "Dieses Handbuch im Workspace. Derselbe Inhalt wie die öffentliche Seite /guida."
    ),
    "Cinque pagine, un dominio attivo, grafici dallo stesso run.": (
        "Fünf Seiten, eine aktive Domain, Diagramme desselben Laufs."
    ),
    "Panoramica: CVI sul marchio (voto DD–AA nel C, punteggio a destra), KPI e grafici": (
        "Übersicht: CVI auf dem Markenzeichen (Note DD–AA im C, Punktzahl rechts), KPIs und Diagramme"
    ),
    "Benchmark, Prompt e Trend sul dominio selezionato dai chip": (
        "Benchmark, Prompt und Trend zur über die Chips gewählten Domain"
    ),
    "Account e impostazioni nel menu avatar — non in una sesta pill": (
        "Konto und Einstellungen im Avatar-Menü — keine sechste Pille"
    ),
    "Indice di criticità: (critici × 100 + warning × 40) / totale, sotto Distribuzione AIO nello stack Crawl": (
        "Kritikalitätsindex: (kritisch × 100 + Warnung × 40) / Gesamt, unter der AIO-Verteilung im Crawl-Stack"
    ),
    "Pack HTML con logo originale, score, finding e snippet da pubblicare.": (
        "HTML-Pack mit Original-Logo, Score, Findings und zu veröffentlichenden Snippets."
    ),
    "Scarica centropic-fix.html: si apre offline, logo in testa": (
        "centropic-fix.html herunterladen: öffnet offline, Original-Logo oben"
    ),
    "Moduli: grafo entità, citabilità, schema, publish verify, llms lint, mercati.": (
        "Module: Entity-Graph, Zitierbarkeit, Schema, Publish Verify, llms lint, Märkte."
    ),
    "Mercati e lingue: hreflang e coerenza": "Märkte und Sprachen: hreflang und Konsistenz",
    "Trend e re-scan": "Trend und Re-Scan",
    "Serie temporale sul dominio attivo: AIO/GEO e CVI, con le date sotto ogni punto.": (
        "Zeitreihe der aktiven Domain: AIO/GEO und CVI, mit Datum unter jedem Punkt."
    ),
    "Due grafici affiancati: AIO/GEO e CVI per run": (
        "Zwei Diagramme nebeneinander: AIO/GEO und CVI pro Lauf"
    ),
    "Ripartizione motori": "Engine-Aufschlüsselung",
    "Grafo entità": "Entity-Graph",
    "Citabilità": "Zitierbarkeit",
    "Qualità schema": "Schema-Qualität",
    "Mercati e lingue": "Märkte und Sprachen",
    "Leggi lettera e score: DD è critico, AA è top. Il voto sta nel marchio, il numero a destra. Mira a salire di almeno un grado CVI tra un re-scan e l’altro.": (
        "Lesen Sie Buchstabe und Score: DD ist kritisch, AA ist top. Die Note sitzt im Markenzeichen, "
        "die Zahl rechts. Ziel: mindestens eine CVI-Stufe zwischen Re-Scans steigen."
    ),
    "Chiudi critical e warn; usa l’indice di criticità e il pack. Poi ripubblica e verifica.": (
        "Schließen Sie kritische und Warn-Findings; nutzen Sie den Kritikalitätsindex und das Pack. Dann neu veröffentlichen und prüfen."
    ),
    "Root del sito: %(path)s — oppure Edge + CMS connector.": (
        "Website-Root: %(path)s — oder Edge + CMS-Connector."
    ),
    "unico deliverable: logo originale in testa; apri e copia head / llms.txt / robots sul sito": (
        "einziges Deliverable: Original-Logo oben; öffnen und head / llms.txt / robots auf die Website kopieren"
    ),
    "Plus · €19,99 Tasse escluse": "Plus · 19,99 € zzgl. Steuern",
    "Business · €89,99 Tasse escluse": "Business · 89,99 € zzgl. Steuern",
    "Metrica proprietaria Centropic: indice 0–100 con lettera DD→AA che sintetizza AIO+GEO (con penalità findings). In Panoramica il voto sta nel marchio; il punteggio numerico sta a destra. È lo standard da confrontare tra brand — non Domain Authority di terzi.": (
        "Proprietäre Centropic-Metrik: Index 0–100 mit Buchstabe DD→AA, der AIO+GEO synthetisiert "
        "(mit Findings-Abzügen). In der Übersicht sitzt die Note im Markenzeichen; die Zahl rechts. "
        "Das ist der Standard zum Markenvergleich — keine Domain Authority Dritter."
    ),
    "Score 0–100 dalla mix dei finding del run: (critici × 100 + warning × 40) / totale. In Panoramica sta sotto Distribuzione AIO, stessa colonna Crawl.": (
        "Score 0–100 aus der Finding-Mischung des Laufs: (kritisch × 100 + Warnung × 40) / Gesamt. "
        "In der Übersicht unter der AIO-Verteilung, dieselbe Crawl-Spalte."
    ),
    "Le cinque pagine del prodotto: Panoramica, Benchmark, Prompt, Trend, Guida. Account e impostazioni restano nel menu avatar.": (
        "Die fünf Produktseiten: Übersicht, Benchmark, Prompt, Trend, Guide. "
        "Konto und Einstellungen bleiben im Avatar-Menü."
    ),
    "Insieme di artifact generati dall’analisi. Il file centropic-fix.html include il logo originale in testa, score, finding e snippet (llms, schema, meta, robots, checklist).": (
        "Artefakte der Analyse. centropic-fix.html enthält das Original-Logo oben, "
        "Score, Findings und Snippets (llms, schema, meta, robots, checklist)."
    ),
    "Il workspace ha cinque pagine: Panoramica, Benchmark, Prompt, Trend, Guida.": (
        "Der Workspace hat fünf Seiten: Übersicht, Benchmark, Prompt, Trend, Guide."
    ),
    "Workspace: CVI sul marchio, grafici AIO/GEO e pack in cinque pagine.": (
        "Workspace: CVI auf dem Markenzeichen, AIO/GEO-Diagramme und Packs auf fünf Seiten."
    ),
    "Stato": "Status",
    "JSON-LD + FAQ + meta": "JSON-LD + FAQ + Meta",
    "API: GET /api/v1/sites/<id>/edge": "API: GET /api/v1/sites/<id>/edge",
    "Finding": "Finding",
    "Pack": "Pack",
    "Quota operativa": "Betriebskontingent",
    "Cosa misuriamo — e cosa no": "Was wir messen — und was nicht",
    "Tre richieste frequenti in discovery restano fuori dal prodotto. Non per roadmap vuota: perché non le possiamo misurare in modo onesto, o perché brucerebbero la quota operativa senza rendere il sito più citabile.": (
        "Drei Fragen, die im Vertrieb oft auftauchen, sind nicht Teil des Produkts. "
        "Das ist keine Lücke in der Roadmap: Wir können sie nicht ehrlich messen — "
        "oder sie würden das Monatskontingent verbrauchen, ohne die Website zitierbarer zu machen."
    ),
    "Attribution e ROI dalle citazioni LLM": "Attribution und ROI aus LLM-Zitaten",
    "ChatGPT, Claude, Perplexity e Copilot non espongono impression, click o CTR. Un “ricavo generato dalla visibilità AI” sarebbe una correlazione inventata. Centropic misura le menzioni sul prompt bank (SoV Misurato) e, su Plus, può collegare Search Console come baseline di Search — non come traffico AI. Quando avremo sessioni con referrer AI dichiarati dal tuo analytics, le metteremo in Trend con l’etichetta Stimato.": (
        "ChatGPT, Claude, Perplexity und Copilot geben keine Impressions, Klicks oder CTR preis. "
        "Eine Zahl für „Umsatz aus KI-Sichtbarkeit“ wäre eine erfundene Korrelation. "
        "Centropic misst Markennennungen anhand Ihrer Prompt-Bank (Measured SoV) und kann auf Plus "
        "die Search Console als Search-Baseline anbinden — nicht als KI-Traffic. "
        "Sobald wir Sitzungen mit KI-Referrern aus Ihrer Analytics haben, "
        "tragen wir sie in Trend ein und kennzeichnen sie als Estimated."
    ),
    "Simulazioni agente (buyer persona / funnel d’acquisto)": (
        "Agentensimulationen (Buyer Personas und Kauf-Funnel)"
    ),
    "Un journey multi-turno (CTO, procurement) moltiplica le probe LLM: un sim pieno può costare quanto 4–10 analisi Misurate e resta stocastico. Oggi il prompt bank su Plus accetta domande in stile buyer; non lanciamo agenti nel POST analyze perché svuoterebbero la quota mensile senza pubblicare un artifact. Se serve un report journey, è uno SKU a parte, non il default.": (
        "Eine mehrstufige Journey (CTO, Einkauf) vervielfacht die LLM-Probes: "
        "eine volle Simulation kann 4–10 Measured-Analysen kosten und bleibt stochastisch. "
        "Die Plus-Prompt-Bank nimmt bereits Fragen im Buyer-Stil entgegen. "
        "Wir starten keine Agenten bei POST /analyze — das würde das Monatskontingent leeren, ohne ein Artifact zu veröffentlichen. "
        "Ein Journey-Report wäre eine eigene SKU, nicht der Standard."
    ),
    "Audit nei dataset di pre-training (Common Crawl, Reddit, “pesi” GPT)": (
        "Prüfung von Pre-Training-Datensätzen (Common Crawl, Reddit, GPT-„Gewichte“)"
    ),
    "Nessun modello chiuso certifica se il brand è nei suoi pesi. Dirlo in dashboard sarebbe un claim commerciale, non una misura. La GEO Suite già legge il tuo sito (grafo entità, sameAs, schema). Una presenza su Wikipedia/Wikidata è un finding utile; “sei nel training di ChatGPT” no. Restiamo su ciò che è osservabile.": (
        "Kein geschlossenes Modell bestätigt, dass Ihre Marke in seinen Gewichten steckt. "
        "Das ins Dashboard zu schreiben wäre eine Marketingbehauptung, keine Messung. "
        "Die GEO Suite liest bereits Ihre Website (Entity-Graph, sameAs, Schema). "
        "Eine Wikipedia-/Wikidata-Präsenz ist ein nützliches Finding; „Sie sind im ChatGPT-Training“ ist keines. "
        "Wir bleiben bei dem, was beobachtbar ist."
    ),
    "Plus/Business: webhook pack.ready (checksum + URL Edge) così il CMS applica senza copiare i file": (
        "Plus/Business: pack.ready-Webhook (Checksummen + Edge-URLs), damit Ihr CMS das Pack anwendet, ohne Dateien zu kopieren"
    ),
    "APPLY.md nello ZIP: evento pack.ready, idempotenza su signals_version": (
        "APPLY.md im ZIP: pack.ready-Ereignis, idempotent über signals_version"
    ),
    "GET /sites/<id> e /runs: AIO, GEO, CVI, SoV, criticità, checksum — OpenAPI in /api/v1/openapi.json": (
        "GET /sites/<id> und /runs: AIO, GEO, CVI, SoV, Kritikalität, Checksummen — OpenAPI unter /api/v1/openapi.json"
    ),
    "Webhook analysis.completed + pack.ready (oltre agli alert di regressione)": (
        "Webhooks analysis.completed und pack.ready (zusätzlich zu Regressions-Alerts)"
    ),
    "Approfondimento su Misurato vs Stimato nella": "Mehr zu Measured vs. Estimated in der",
    "Eventi: analysis.completed, pack.ready (checksum + URL Edge, senza body dei file), analysis.alert (solo regressioni).": (
        "Ereignisse: analysis.completed, pack.ready (Checksummen + Edge-URLs, ohne Datei-Bodies), analysis.alert (nur Regressionen)."
    ),
    "Firma HMAC in X-Centropic-Signature. Applica pack.ready una volta per idempotency_key.": (
        "HMAC-Signatur in X-Centropic-Signature. pack.ready einmal pro idempotency_key anwenden."
    ),
}

ES = {
    "Panoramica": "Panorámica",
    "Benchmark": "Benchmark",
    "Prompt": "Prompt",
    "Trend": "Tendencia",
    "Dominio attivo": "Dominio activo",
    "Nuovo dominio": "Nuevo dominio",
    "Distribuzione AIO": "Distribución AIO",
    "Indice di criticità": "Índice de criticidad",
    "Composizione": "Composición",
    "Motori": "Motores",
    "Ledger": "Libro",
    "Aperti": "Abiertos",
    "Pagine": "Páginas",
    "Findings e pack": "Findings y pack",
    "Cerca o incolla URL": "Busca o pega la URL",
    "Seleziona dominio": "Seleccionar dominio",
    "Audit": "Auditoría",
    "Mix": "Mix",
    "Campo": "Campo",
    "Andamento AIO e GEO": "Evolución AIO y GEO",
    "AIO / GEO per data": "AIO / GEO por fecha",
    "Vai alla Panoramica": "Ir a Panorámica",
    "Findings aperti e deliverable da applicare.": "Findings abiertos y entregables que aplicar.",
    "aperti sul run analizzato": "abiertos en el run analizado",
    "Pagine per fascia AIO": "Páginas por franja AIO",
    "Nessun breakdown disponibile.": "No hay desglose disponible.",
    "Nessuna pagina con score AIO.": "No hay páginas con puntuación AIO.",
    "Nessuna criticità aperta.": "No hay incidencias abiertas.",
    "Nessuna pagina in crawl.": "No hay páginas en el crawl.",
    "Nessuna analisi ancora": "Aún no hay análisis",
    "Competitor (max 3)": "Competidores (máx. 3)",
    "Aggiungi competitor": "Añadir competidor",
    "Deep crawl": "Crawl profundo",
    "Saldo token": "Saldo de tokens",
    "Metriche": "Métricas",
    "Metriche primarie": "Métricas primarias",
    "Critici": "Críticos",
    "Warn": "Aviso",
    "Italia": "Italia",
    "https://tuosito.com": "https://tusitio.es",
    "https://iltuosito.it": "https://tusitio.es",
    "https://rivale.com": "https://rival.es",
    "https://rivale1.com": "https://rival1.es",
    "https://rivale2.com": "https://rival2.es",
    "https://tuodominio/llms.txt": "https://tudominio.es/llms.txt",
    "21 agosto 2026": "21 de agosto de 2026",
    "Come leggere il workspace: le cinque pagine, il CVI sul marchio, i grafici AIO/GEO, l’indice di criticità, i pack e l’Edge.": (
        "Cómo leer el workspace: las cinco páginas, el CVI en la marca, "
        "los gráficos AIO/GEO, el índice de criticidad, los packs y Edge."
    ),
    "Le cinque pagine": "Las cinco páginas",
    "Il workspace ha una sola barra in alto. Cinque destinazioni, stesso dominio attivo. Account e impostazioni restano nel menu avatar.": (
        "El workspace tiene una sola barra arriba. Cinco destinos, el mismo dominio activo. "
        "La cuenta y los ajustes quedan en el menú del avatar."
    ),
    "Dominio e CVI in testa. Sotto: sette KPI, Composizione e Motori alla stessa altezza, poi Suite e Mix, poi Crawl AIO con Distribuzione AIO e Indice di criticità nella stessa colonna, ledger pagine a destra. In coda: storico run e findings.": (
        "Dominio y CVI arriba. Debajo: siete KPI, Composición y Motores a la misma altura, "
        "luego Suite y Mix, luego Crawl AIO con Distribución AIO e Índice de criticidad "
        "en la misma columna, libro de páginas a la derecha. Al final: historial de runs y findings."
    ),
    "Confronta il sito attivo con i rivali su AIO, GEO, SoV e motori. Usa uno snapshot già misurato, non un grafico inventato.": (
        "Compara el sitio activo con los rivales en AIO, GEO, SoV y motores. "
        "Usa una instantánea ya medida, no un gráfico inventado."
    ),
    "Le query usate per misurare il SoV e i finding aperti. Qui si vede cosa è stato chiesto ai motori e il pack da applicare.": (
        "Las consultas usadas para medir el SoV y los findings abiertos. "
        "Aquí se ve qué se preguntó a los motores y el pack que aplicar."
    ),
    "Storico delle run sul dominio attivo. Due grafici affiancati: AIO/GEO nel tempo e CVI per run, con le date sotto ogni punto. Serve almeno due analisi.": (
        "Historial de runs del dominio activo. Dos gráficos lado a lado: AIO/GEO en el tiempo "
        "y CVI por run, con fechas bajo cada punto. Hacen falta al menos dos análisis."
    ),
    "Questo manuale, dentro il workspace. Stesso contenuto della pagina pubblica /guida.": (
        "Este manual, dentro del workspace. El mismo contenido que la página pública /guida."
    ),
    "Cinque pagine, un dominio attivo, grafici dallo stesso run.": (
        "Cinco páginas, un dominio activo, gráficos del mismo run."
    ),
    "Panoramica: CVI sul marchio (voto DD–AA nel C, punteggio a destra), KPI e grafici": (
        "Panorámica: CVI en la marca (nota DD–AA dentro de la C, puntuación a la derecha), KPI y gráficos"
    ),
    "Benchmark, Prompt e Trend sul dominio selezionato dai chip": (
        "Benchmark, Prompt y Tendencia en el dominio elegido con los chips"
    ),
    "Account e impostazioni nel menu avatar — non in una sesta pill": (
        "Cuenta y ajustes en el menú del avatar — no una sexta pastilla"
    ),
    "Indice di criticità: (critici × 100 + warning × 40) / totale, sotto Distribuzione AIO nello stack Crawl": (
        "Índice de criticidad: (críticos × 100 + avisos × 40) / total, bajo Distribución AIO en la pila Crawl"
    ),
    "Pack HTML con logo originale, score, finding e snippet da pubblicare.": (
        "Pack HTML con el logo original, puntuación, findings y snippets para publicar."
    ),
    "Scarica centropic-fix.html: si apre offline, logo in testa": (
        "Descarga centropic-fix.html: se abre sin conexión, logo original arriba"
    ),
    "Moduli: grafo entità, citabilità, schema, publish verify, llms lint, mercati.": (
        "Módulos: grafo de entidades, citabilidad, schema, publish verify, llms lint, mercados."
    ),
    "Mercati e lingue: hreflang e coerenza": "Mercados e idiomas: hreflang y coherencia",
    "Trend e re-scan": "Tendencia y re-scan",
    "Serie temporale sul dominio attivo: AIO/GEO e CVI, con le date sotto ogni punto.": (
        "Serie temporal del dominio activo: AIO/GEO y CVI, con fechas bajo cada punto."
    ),
    "Due grafici affiancati: AIO/GEO e CVI per run": (
        "Dos gráficos lado a lado: AIO/GEO y CVI por run"
    ),
    "Ripartizione motori": "Desglose por motor",
    "Grafo entità": "Grafo de entidades",
    "Citabilità": "Citabilidad",
    "Qualità schema": "Calidad del schema",
    "Mercati e lingue": "Mercados e idiomas",
    "Leggi lettera e score: DD è critico, AA è top. Il voto sta nel marchio, il numero a destra. Mira a salire di almeno un grado CVI tra un re-scan e l’altro.": (
        "Lee la letra y la puntuación: DD es crítico, AA es top. La nota está en la marca, "
        "el número a la derecha. Intenta subir al menos un grado CVI entre re-scans."
    ),
    "Chiudi critical e warn; usa l’indice di criticità e il pack. Poi ripubblica e verifica.": (
        "Cierra los críticos y avisos; usa el índice de criticidad y el pack. Luego republica y verifica."
    ),
    "Root del sito: %(path)s — oppure Edge + CMS connector.": (
        "Raíz del sitio: %(path)s — o Edge + conector CMS."
    ),
    "unico deliverable: logo originale in testa; apri e copia head / llms.txt / robots sul sito": (
        "único entregable: logo original arriba; abre y copia head / llms.txt / robots en el sitio"
    ),
    "Plus · €19,99 Tasse escluse": "Plus · 19,99 € impuestos excluidos",
    "Business · €89,99 Tasse escluse": "Business · 89,99 € impuestos excluidos",
    "Metrica proprietaria Centropic: indice 0–100 con lettera DD→AA che sintetizza AIO+GEO (con penalità findings). In Panoramica il voto sta nel marchio; il punteggio numerico sta a destra. È lo standard da confrontare tra brand — non Domain Authority di terzi.": (
        "Métrica propietaria de Centropic: índice 0–100 con letra DD→AA que sintetiza AIO+GEO "
        "(con penalización por findings). En Panorámica la nota está en la marca; la puntuación a la derecha. "
        "Es el estándar para comparar marcas — no Domain Authority de terceros."
    ),
    "Score 0–100 dalla mix dei finding del run: (critici × 100 + warning × 40) / totale. In Panoramica sta sotto Distribuzione AIO, stessa colonna Crawl.": (
        "Puntuación 0–100 de la mezcla de findings del run: (críticos × 100 + avisos × 40) / total. "
        "En Panorámica está bajo Distribución AIO, misma columna Crawl."
    ),
    "Le cinque pagine del prodotto: Panoramica, Benchmark, Prompt, Trend, Guida. Account e impostazioni restano nel menu avatar.": (
        "Las cinco páginas del producto: Panorámica, Benchmark, Prompt, Tendencia, Guía. "
        "La cuenta y los ajustes quedan en el menú del avatar."
    ),
    "Insieme di artifact generati dall’analisi. Il file centropic-fix.html include il logo originale in testa, score, finding e snippet (llms, schema, meta, robots, checklist).": (
        "Conjunto de artefactos del análisis. centropic-fix.html incluye el logo original arriba, "
        "puntuación, findings y snippets (llms, schema, meta, robots, checklist)."
    ),
    "Il workspace ha cinque pagine: Panoramica, Benchmark, Prompt, Trend, Guida.": (
        "El workspace tiene cinco páginas: Panorámica, Benchmark, Prompt, Tendencia, Guía."
    ),
    "Workspace: CVI sul marchio, grafici AIO/GEO e pack in cinque pagine.": (
        "Workspace: CVI en la marca, gráficos AIO/GEO y packs en cinco páginas."
    ),
    "Stato": "Estado",
    "JSON-LD + FAQ + meta": "JSON-LD + FAQ + meta",
    "API: GET /api/v1/sites/<id>/edge": "API: GET /api/v1/sites/<id>/edge",
    "Finding": "Finding",
    "Pack": "Pack",
    "Quota operativa": "Cuota operativa",
    "Cosa misuriamo — e cosa no": "Qué medimos — y qué no",
    "Tre richieste frequenti in discovery restano fuori dal prodotto. Non per roadmap vuota: perché non le possiamo misurare in modo onesto, o perché brucerebbero la quota operativa senza rendere il sito più citabile.": (
        "Tres preguntas que salen a menudo en las conversaciones de venta no están en el producto. "
        "No es un hueco en la hoja de ruta: no podemos medirlas con honestidad, "
        "o consumirían la cuota mensual sin hacer el sitio más citable."
    ),
    "Attribution e ROI dalle citazioni LLM": "Atribución y ROI a partir de citas en LLM",
    "ChatGPT, Claude, Perplexity e Copilot non espongono impression, click o CTR. Un “ricavo generato dalla visibilità AI” sarebbe una correlazione inventata. Centropic misura le menzioni sul prompt bank (SoV Misurato) e, su Plus, può collegare Search Console come baseline di Search — non come traffico AI. Quando avremo sessioni con referrer AI dichiarati dal tuo analytics, le metteremo in Trend con l’etichetta Stimato.": (
        "ChatGPT, Claude, Perplexity y Copilot no exponen impresiones, clics ni CTR. "
        "Un “ingreso por visibilidad IA” sería una correlación inventada. "
        "Centropic mide menciones de marca frente a tu banco de prompts (SoV Medido) y, en Plus, "
        "puede conectar Search Console como baseline de Search — no como tráfico IA. "
        "Cuando tengamos sesiones con referrer IA declarados por tu analítica, "
        "las pondremos en Trend con la etiqueta Estimado."
    ),
    "Simulazioni agente (buyer persona / funnel d’acquisto)": (
        "Simulaciones con agentes (buyer personas y embudo de compra)"
    ),
    "Un journey multi-turno (CTO, procurement) moltiplica le probe LLM: un sim pieno può costare quanto 4–10 analisi Misurate e resta stocastico. Oggi il prompt bank su Plus accetta domande in stile buyer; non lanciamo agenti nel POST analyze perché svuoterebbero la quota mensile senza pubblicare un artifact. Se serve un report journey, è uno SKU a parte, non il default.": (
        "Un recorrido de varios turnos (CTO, compras) multiplica las pruebas LLM: "
        "una simulación completa puede costar tanto como 4–10 análisis Medidos y sigue siendo estocástica. "
        "El banco de prompts de Plus ya acepta preguntas al estilo del comprador. "
        "No lanzamos agentes en el POST /analyze: vaciarían la cuota mensual sin publicar un artefacto. "
        "Si necesitas un informe de recorrido, es un SKU aparte, no el valor por defecto."
    ),
    "Audit nei dataset di pre-training (Common Crawl, Reddit, “pesi” GPT)": (
        "Auditoría de datos de preentrenamiento (Common Crawl, Reddit, “pesos” de GPT)"
    ),
    "Nessun modello chiuso certifica se il brand è nei suoi pesi. Dirlo in dashboard sarebbe un claim commerciale, non una misura. La GEO Suite già legge il tuo sito (grafo entità, sameAs, schema). Una presenza su Wikipedia/Wikidata è un finding utile; “sei nel training di ChatGPT” no. Restiamo su ciò che è osservabile.": (
        "Ningún modelo cerrado certifica que tu marca esté en sus pesos. "
        "Decirlo en el panel sería una afirmación comercial, no una medida. "
        "La GEO Suite ya lee tu sitio (grafo de entidades, sameAs, schema). "
        "Una presencia en Wikipedia/Wikidata es un hallazgo útil; “estás en el entrenamiento de ChatGPT” no lo es. "
        "Nos quedamos con lo observable."
    ),
    "Plus/Business: webhook pack.ready (checksum + URL Edge) così il CMS applica senza copiare i file": (
        "Plus/Business: webhook pack.ready (checksums + URL Edge) para que tu CMS aplique el pack sin copiar archivos"
    ),
    "APPLY.md nello ZIP: evento pack.ready, idempotenza su signals_version": (
        "APPLY.md en el ZIP: evento pack.ready, idempotente sobre signals_version"
    ),
    "GET /sites/<id> e /runs: AIO, GEO, CVI, SoV, criticità, checksum — OpenAPI in /api/v1/openapi.json": (
        "GET /sites/<id> y /runs: AIO, GEO, CVI, SoV, criticidad, checksums — OpenAPI en /api/v1/openapi.json"
    ),
    "Webhook analysis.completed + pack.ready (oltre agli alert di regressione)": (
        "Webhooks analysis.completed y pack.ready (además de las alertas de regresión)"
    ),
    "Approfondimento su Misurato vs Stimato nella": "Más sobre Medido vs Estimado en la",
    "Eventi: analysis.completed, pack.ready (checksum + URL Edge, senza body dei file), analysis.alert (solo regressioni).": (
        "Eventos: analysis.completed, pack.ready (checksums + URL Edge, sin cuerpos de archivo), analysis.alert (solo regresiones)."
    ),
    "Firma HMAC in X-Centropic-Signature. Applica pack.ready una volta per idempotency_key.": (
        "HMAC en X-Centropic-Signature. Aplica pack.ready una vez por idempotency_key."
    ),
}

ZH = {
    "Panoramica": "概览",
    "Benchmark": "对标",
    "Prompt": "提示词",
    "Trend": "趋势",
    "Dominio attivo": "当前域名",
    "Nuovo dominio": "新域名",
    "Distribuzione AIO": "AIO 分布",
    "Indice di criticità": "严重度指数",
    "Composizione": "构成",
    "Motori": "引擎",
    "Ledger": "账本",
    "Aperti": "未关闭",
    "Pagine": "页面",
    "Findings e pack": "Findings 与数据包",
    "Cerca o incolla URL": "搜索或粘贴 URL",
    "Seleziona dominio": "选择域名",
    "Audit": "审计",
    "Mix": "构成比",
    "Campo": "场域",
    "Andamento AIO e GEO": "AIO 与 GEO 走势",
    "AIO / GEO per data": "按日期的 AIO / GEO",
    "Vai alla Panoramica": "前往概览",
    "Findings aperti e deliverable da applicare.": "待处理 Findings 与需应用的交付物。",
    "aperti sul run analizzato": "本轮分析中未关闭",
    "Pagine per fascia AIO": "按 AIO 区间的页面",
    "Nessun breakdown disponibile.": "暂无拆分。",
    "Nessuna pagina con score AIO.": "没有带 AIO 分数的页面。",
    "Nessuna criticità aperta.": "没有未关闭的问题。",
    "Nessuna pagina in crawl.": "抓取中没有页面。",
    "Nessuna analisi ancora": "尚无分析",
    "Competitor (max 3)": "竞品（最多 3 个）",
    "Aggiungi competitor": "添加竞品",
    "Deep crawl": "深度抓取",
    "Saldo token": "代币余额",
    "Metriche": "指标",
    "Metriche primarie": "主要指标",
    "Critici": "严重",
    "Warn": "警告",
    "Italia": "意大利",
    "https://tuosito.com": "https://yoursite.com",
    "https://iltuosito.it": "https://yoursite.com",
    "https://rivale.com": "https://rival.com",
    "https://rivale1.com": "https://rival1.com",
    "https://rivale2.com": "https://rival2.com",
    "https://tuodominio/llms.txt": "https://yourdomain.com/llms.txt",
    "21 agosto 2026": "2026年8月21日",
    "Come leggere il workspace: le cinque pagine, il CVI sul marchio, i grafici AIO/GEO, l’indice di criticità, i pack e l’Edge.": (
        "如何阅读工作区：五个页面、标志上的 CVI、AIO/GEO 图表、严重度指数、数据包与 Edge。"
    ),
    "Le cinque pagine": "五个页面",
    "Il workspace ha una sola barra in alto. Cinque destinazioni, stesso dominio attivo. Account e impostazioni restano nel menu avatar.": (
        "工作区顶部只有一条栏。五个入口，同一当前域名。账户与设置留在头像菜单。"
    ),
    "Dominio e CVI in testa. Sotto: sette KPI, Composizione e Motori alla stessa altezza, poi Suite e Mix, poi Crawl AIO con Distribuzione AIO e Indice di criticità nella stessa colonna, ledger pagine a destra. In coda: storico run e findings.": (
        "顶部是域名与 CVI。下方：七个 KPI、同高的构成与引擎，然后是套件与构成比，"
        "再是同一列中的 AIO 抓取分布与严重度指数，右侧为页面账本。底部是运行历史与 Findings。"
    ),
    "Confronta il sito attivo con i rivali su AIO, GEO, SoV e motori. Usa uno snapshot già misurato, non un grafico inventato.": (
        "按 AIO、GEO、SoV 和引擎对比当前站点与竞品。使用已测量的快照，不是虚构图表。"
    ),
    "Le query usate per misurare il SoV e i finding aperti. Qui si vede cosa è stato chiesto ai motori e il pack da applicare.": (
        "用于测量 SoV 的查询以及未关闭的 Findings。可查看向引擎提出的问题与需应用的数据包。"
    ),
    "Storico delle run sul dominio attivo. Due grafici affiancati: AIO/GEO nel tempo e CVI per run, con le date sotto ogni punto. Serve almeno due analisi.": (
        "当前域名的运行历史。并排两张图：随时间的 AIO/GEO 与每次运行的 CVI，每个点下方有日期。至少需要两次分析。"
    ),
    "Questo manuale, dentro il workspace. Stesso contenuto della pagina pubblica /guida.": (
        "工作区内的本手册。与公开页 /guida 内容相同。"
    ),
    "Cinque pagine, un dominio attivo, grafici dallo stesso run.": (
        "五个页面、一个当前域名、来自同一轮分析的图表。"
    ),
    "Panoramica: CVI sul marchio (voto DD–AA nel C, punteggio a destra), KPI e grafici": (
        "概览：标志上的 CVI（C 内为 DD–AA 等级，右侧为分数）、KPI 与图表"
    ),
    "Benchmark, Prompt e Trend sul dominio selezionato dai chip": (
        "通过芯片所选域名的对标、提示词与趋势"
    ),
    "Account e impostazioni nel menu avatar — non in una sesta pill": (
        "账户与设置在头像菜单中 — 不是第六个标签"
    ),
    "Indice di criticità: (critici × 100 + warning × 40) / totale, sotto Distribuzione AIO nello stack Crawl": (
        "严重度指数：(严重 × 100 + 警告 × 40) / 总数，位于抓取栈中 AIO 分布下方"
    ),
    "Pack HTML con logo originale, score, finding e snippet da pubblicare.": (
        "带原版标志、分数、Findings 与待发布片段的 HTML 数据包。"
    ),
    "Scarica centropic-fix.html: si apre offline, logo in testa": (
        "下载 centropic-fix.html：可离线打开，顶部为原版标志"
    ),
    "Moduli: grafo entità, citabilità, schema, publish verify, llms lint, mercati.": (
        "模块：实体图、可引用性、schema、发布校验、llms lint、市场。"
    ),
    "Mercati e lingue: hreflang e coerenza": "市场与语言：hreflang 与一致性",
    "Trend e re-scan": "趋势与重新扫描",
    "Serie temporale sul dominio attivo: AIO/GEO e CVI, con le date sotto ogni punto.": (
        "当前域名的时间序列：AIO/GEO 与 CVI，每个点下方有日期。"
    ),
    "Due grafici affiancati: AIO/GEO e CVI per run": (
        "并排两张图：每次运行的 AIO/GEO 与 CVI"
    ),
    "Ripartizione motori": "引擎拆分",
    "Grafo entità": "实体图",
    "Citabilità": "可引用性",
    "Qualità schema": "Schema 质量",
    "Mercati e lingue": "市场与语言",
    "Leggi lettera e score: DD è critico, AA è top. Il voto sta nel marchio, il numero a destra. Mira a salire di almeno un grado CVI tra un re-scan e l’altro.": (
        "阅读等级与分数：DD 为危急，AA 为优秀。等级在标志内，数字在右侧。两次重新扫描之间至少提升一个 CVI 等级。"
    ),
    "Chiudi critical e warn; usa l’indice di criticità e il pack. Poi ripubblica e verifica.": (
        "先关闭严重与警告项；使用严重度指数和数据包。然后重新发布并校验。"
    ),
    "Root del sito: %(path)s — oppure Edge + CMS connector.": (
        "网站根目录：%(path)s — 或使用 Edge + CMS 连接器。"
    ),
    "unico deliverable: logo originale in testa; apri e copia head / llms.txt / robots sul sito": (
        "唯一交付物：顶部为原版标志；打开并复制 head / llms.txt / robots 到网站"
    ),
    "Plus · €19,99 Tasse escluse": "Plus · €19.99 不含税",
    "Business · €89,99 Tasse escluse": "Business · €89.99 不含税",
    "Metrica proprietaria Centropic: indice 0–100 con lettera DD→AA che sintetizza AIO+GEO (con penalità findings). In Panoramica il voto sta nel marchio; il punteggio numerico sta a destra. È lo standard da confrontare tra brand — non Domain Authority di terzi.": (
        "Centropic 专有指标：0–100 指数配 DD→AA 字母，综合 AIO+GEO（含 Findings 罚分）。"
        "在概览中，等级位于标志内，数字分数在右侧。这是品牌对比标准 — 不是第三方 Domain Authority。"
    ),
    "Score 0–100 dalla mix dei finding del run: (critici × 100 + warning × 40) / totale. In Panoramica sta sotto Distribuzione AIO, stessa colonna Crawl.": (
        "由本轮 Findings 混合得出的 0–100 分数：(严重 × 100 + 警告 × 40) / 总数。"
        "在概览中位于 AIO 分布下方，同一抓取列。"
    ),
    "Le cinque pagine del prodotto: Panoramica, Benchmark, Prompt, Trend, Guida. Account e impostazioni restano nel menu avatar.": (
        "产品的五个页面：概览、对标、提示词、趋势、指南。账户与设置留在头像菜单。"
    ),
    "Insieme di artifact generati dall’analisi. Il file centropic-fix.html include il logo originale in testa, score, finding e snippet (llms, schema, meta, robots, checklist).": (
        "分析生成的产物集。centropic-fix.html 顶部含原版标志，以及分数、Findings 与片段（llms、schema、meta、robots、清单）。"
    ),
    "Il workspace ha cinque pagine: Panoramica, Benchmark, Prompt, Trend, Guida.": (
        "工作区有五个页面：概览、对标、提示词、趋势、指南。"
    ),
    "Workspace: CVI sul marchio, grafici AIO/GEO e pack in cinque pagine.": (
        "工作区：标志上的 CVI、AIO/GEO 图表，以及五个页面中的数据包。"
    ),
    "Stato": "状态",
    "JSON-LD + FAQ + meta": "JSON-LD + FAQ + meta",
    "API: GET /api/v1/sites/<id>/edge": "API: GET /api/v1/sites/<id>/edge",
    "Finding": "Finding",
    "Pack": "数据包",
    "Quota operativa": "运营配额",
    "Cosa misuriamo — e cosa no": "我们测什么，不测什么",
    "Tre richieste frequenti in discovery restano fuori dal prodotto. Non per roadmap vuota: perché non le possiamo misurare in modo onesto, o perché brucerebbero la quota operativa senza rendere il sito più citabile.": (
        "销售里常被问到的三件事，产品里没有。不是路线图空着：要么没法老实测，"
        "要么会把月度配额烧光，却不能让网站更好被引用。"
    ),
    "Attribution e ROI dalle citazioni LLM": "来自大模型引用的归因与 ROI",
    "ChatGPT, Claude, Perplexity e Copilot non espongono impression, click o CTR. Un “ricavo generato dalla visibilità AI” sarebbe una correlazione inventata. Centropic misura le menzioni sul prompt bank (SoV Misurato) e, su Plus, può collegare Search Console come baseline di Search — non come traffico AI. Quando avremo sessioni con referrer AI dichiarati dal tuo analytics, le metteremo in Trend con l’etichetta Stimato.": (
        "ChatGPT、Claude、Perplexity 和 Copilot 不提供曝光、点击或 CTR。"
        "所谓“AI 可见度带来的收入”只会是编造的相关性。"
        "Centropic 对照提示词库测量品牌提及（实测 SoV）；Plus 还可连接 Search Console 作为搜索基线——不是 AI 流量。"
        "等你的分析工具能提供带 AI 引荐的会话时，我们会放进趋势并标为估算。"
    ),
    "Simulazioni agente (buyer persona / funnel d’acquisto)": (
        "智能体模拟（买家角色与购买漏斗）"
    ),
    "Un journey multi-turno (CTO, procurement) moltiplica le probe LLM: un sim pieno può costare quanto 4–10 analisi Misurate e resta stocastico. Oggi il prompt bank su Plus accetta domande in stile buyer; non lanciamo agenti nel POST analyze perché svuoterebbero la quota mensile senza pubblicare un artifact. Se serve un report journey, è uno SKU a parte, non il default.": (
        "多轮旅程（CTO、采购）会成倍增加大模型探测次数：一次完整模拟的成本相当于 4–10 次实测分析，而且结果仍带随机性。"
        "Plus 的提示词库已支持采购口吻的问题。"
        "我们不会在 POST /analyze 里启动智能体：那会掏空月度配额，却发不出任何产物。"
        "若需要旅程报告，那是单独 SKU，不是默认项。"
    ),
    "Audit nei dataset di pre-training (Common Crawl, Reddit, “pesi” GPT)": (
        "预训练数据集审计（Common Crawl、Reddit、GPT「权重」）"
    ),
    "Nessun modello chiuso certifica se il brand è nei suoi pesi. Dirlo in dashboard sarebbe un claim commerciale, non una misura. La GEO Suite già legge il tuo sito (grafo entità, sameAs, schema). Una presenza su Wikipedia/Wikidata è un finding utile; “sei nel training di ChatGPT” no. Restiamo su ciò che è osservabile.": (
        "没有任何封闭模型会证明你的品牌在其权重里。"
        "写在仪表盘上只是营销说法，不是测量。"
        "GEO Suite 已经读取你的站点（实体图、sameAs、schema）。"
        "维基百科/维基数据上的存在是有用的发现；“你在 ChatGPT 的训练集里”不是。"
        "我们只做能观察到的事。"
    ),
    "Plus/Business: webhook pack.ready (checksum + URL Edge) così il CMS applica senza copiare i file": (
        "Plus/Business：pack.ready webhook（校验和 + Edge 地址），CMS 无需复制文件即可应用 pack"
    ),
    "APPLY.md nello ZIP: evento pack.ready, idempotenza su signals_version": (
        "ZIP 内的 APPLY.md：pack.ready 事件，按 signals_version 幂等"
    ),
    "GET /sites/<id> e /runs: AIO, GEO, CVI, SoV, criticità, checksum — OpenAPI in /api/v1/openapi.json": (
        "GET /sites/<id> 与 /runs：AIO、GEO、CVI、SoV、严重度、校验和 — OpenAPI 见 /api/v1/openapi.json"
    ),
    "Webhook analysis.completed + pack.ready (oltre agli alert di regressione)": (
        "analysis.completed 与 pack.ready webhook（另有回归告警）"
    ),
    "Approfondimento su Misurato vs Stimato nella": "关于「实测 vs 估算」，详见",
    "Eventi: analysis.completed, pack.ready (checksum + URL Edge, senza body dei file), analysis.alert (solo regressioni).": (
        "事件：analysis.completed、pack.ready（校验和 + Edge 地址，不含文件正文）、analysis.alert（仅回归）。"
    ),
    "Firma HMAC in X-Centropic-Signature. Applica pack.ready una volta per idempotency_key.": (
        "HMAC 签名在 X-Centropic-Signature 中。每个 idempotency_key 只应用一次 pack.ready。"
    ),
}

KO = {
    "Panoramica": "개요",
    "Benchmark": "벤치마크",
    "Prompt": "프롬프트",
    "Trend": "트렌드",
    "Dominio attivo": "활성 도메인",
    "Nuovo dominio": "새 도메인",
    "Distribuzione AIO": "AIO 분포",
    "Indice di criticità": "심각도 지수",
    "Composizione": "구성",
    "Motori": "엔진",
    "Ledger": "원장",
    "Aperti": "미해결",
    "Pagine": "페이지",
    "Findings e pack": "Findings와 팩",
    "Cerca o incolla URL": "URL 검색 또는 붙여넣기",
    "Seleziona dominio": "도메인 선택",
    "Audit": "감사",
    "Mix": "믹스",
    "Campo": "필드",
    "Andamento AIO e GEO": "AIO·GEO 추이",
    "AIO / GEO per data": "날짜별 AIO / GEO",
    "Vai alla Panoramica": "개요로 이동",
    "Findings aperti e deliverable da applicare.": "미해결 Findings와 적용할 산출물.",
    "aperti sul run analizzato": "분석된 런에서 미해결",
    "Pagine per fascia AIO": "AIO 구간별 페이지",
    "Nessun breakdown disponibile.": "세부 내역이 없습니다.",
    "Nessuna pagina con score AIO.": "AIO 점수가 있는 페이지가 없습니다.",
    "Nessuna criticità aperta.": "열린 이슈가 없습니다.",
    "Nessuna pagina in crawl.": "크롤에 페이지가 없습니다.",
    "Nessuna analisi ancora": "아직 분석이 없습니다",
    "Competitor (max 3)": "경쟁사 (최대 3)",
    "Aggiungi competitor": "경쟁사 추가",
    "Deep crawl": "딥 크롤",
    "Saldo token": "토큰 잔액",
    "Metriche": "지표",
    "Metriche primarie": "주요 지표",
    "Critici": "치명",
    "Warn": "경고",
    "Italia": "이탈리아",
    "https://tuosito.com": "https://yoursite.com",
    "https://iltuosito.it": "https://yoursite.com",
    "https://rivale.com": "https://rival.com",
    "https://rivale1.com": "https://rival1.com",
    "https://rivale2.com": "https://rival2.com",
    "https://tuodominio/llms.txt": "https://yourdomain.com/llms.txt",
    "21 agosto 2026": "2026년 8월 21일",
    "Come leggere il workspace: le cinque pagine, il CVI sul marchio, i grafici AIO/GEO, l’indice di criticità, i pack e l’Edge.": (
        "워크스페이스 읽는 법: 다섯 페이지, 마크 위의 CVI, AIO/GEO 차트, 심각도 지수, 팩, Edge."
    ),
    "Le cinque pagine": "다섯 페이지",
    "Il workspace ha una sola barra in alto. Cinque destinazioni, stesso dominio attivo. Account e impostazioni restano nel menu avatar.": (
        "워크스페이스 상단 바는 하나입니다. 다섯 목적지, 같은 활성 도메인. "
        "계정과 설정은 아바타 메뉴에 있습니다."
    ),
    "Dominio e CVI in testa. Sotto: sette KPI, Composizione e Motori alla stessa altezza, poi Suite e Mix, poi Crawl AIO con Distribuzione AIO e Indice di criticità nella stessa colonna, ledger pagine a destra. In coda: storico run e findings.": (
        "상단에 도메인과 CVI. 아래: 일곱 KPI, 같은 높이의 구성과 엔진, "
        "이어서 스위트와 믹스, 같은 열의 AIO 크롤 분포와 심각도 지수, 오른쪽 페이지 원장. 맨 아래는 런 기록과 Findings."
    ),
    "Confronta il sito attivo con i rivali su AIO, GEO, SoV e motori. Usa uno snapshot già misurato, non un grafico inventato.": (
        "활성 사이트를 경쟁사와 AIO, GEO, SoV, 엔진 기준으로 비교합니다. "
        "측정된 스냅샷을 쓰며, 만든 차트는 쓰지 않습니다."
    ),
    "Le query usate per misurare il SoV e i finding aperti. Qui si vede cosa è stato chiesto ai motori e il pack da applicare.": (
        "SoV 측정에 쓴 질의와 미해결 Findings. 엔진에 물은 내용과 적용할 팩을 봅니다."
    ),
    "Storico delle run sul dominio attivo. Due grafici affiancati: AIO/GEO nel tempo e CVI per run, con le date sotto ogni punto. Serve almeno due analisi.": (
        "활성 도메인의 런 기록. 나란히 두 차트: 시간의 AIO/GEO와 런별 CVI, 각 점 아래 날짜. 분석이 두 번 이상 필요합니다."
    ),
    "Questo manuale, dentro il workspace. Stesso contenuto della pagina pubblica /guida.": (
        "워크스페이스 안의 이 매뉴얼. 공개 /guida 페이지와 같은 내용입니다."
    ),
    "Cinque pagine, un dominio attivo, grafici dallo stesso run.": (
        "다섯 페이지, 하나의 활성 도메인, 같은 런의 차트."
    ),
    "Panoramica: CVI sul marchio (voto DD–AA nel C, punteggio a destra), KPI e grafici": (
        "개요: 마크 위의 CVI(C 안 DD–AA 등급, 오른쪽 점수), KPI와 차트"
    ),
    "Benchmark, Prompt e Trend sul dominio selezionato dai chip": (
        "칩으로 고른 도메인의 벤치마크, 프롬프트, 트렌드"
    ),
    "Account e impostazioni nel menu avatar — non in una sesta pill": (
        "계정과 설정은 아바타 메뉴 — 여섯 번째 탭이 아닙니다"
    ),
    "Indice di criticità: (critici × 100 + warning × 40) / totale, sotto Distribuzione AIO nello stack Crawl": (
        "심각도 지수: (치명 × 100 + 경고 × 40) / 전체, 크롤 스택의 AIO 분포 아래"
    ),
    "Pack HTML con logo originale, score, finding e snippet da pubblicare.": (
        "원본 로고, 점수, Findings, 게시할 스니펫이 담긴 HTML 팩."
    ),
    "Scarica centropic-fix.html: si apre offline, logo in testa": (
        "centropic-fix.html 다운로드: 오프라인으로 열리고 상단에 원본 로고"
    ),
    "Moduli: grafo entità, citabilità, schema, publish verify, llms lint, mercati.": (
        "모듈: 엔터티 그래프, 인용 가능성, 스키마, publish verify, llms lint, 시장."
    ),
    "Mercati e lingue: hreflang e coerenza": "시장과 언어: hreflang과 일관성",
    "Trend e re-scan": "트렌드와 재스캔",
    "Serie temporale sul dominio attivo: AIO/GEO e CVI, con le date sotto ogni punto.": (
        "활성 도메인의 시계열: AIO/GEO와 CVI, 각 점 아래 날짜."
    ),
    "Due grafici affiancati: AIO/GEO e CVI per run": (
        "나란히 두 차트: 런별 AIO/GEO와 CVI"
    ),
    "Ripartizione motori": "엔진 분해",
    "Grafo entità": "엔터티 그래프",
    "Citabilità": "인용 가능성",
    "Qualità schema": "스키마 품질",
    "Mercati e lingue": "시장과 언어",
    "Leggi lettera e score: DD è critico, AA è top. Il voto sta nel marchio, il numero a destra. Mira a salire di almeno un grado CVI tra un re-scan e l’altro.": (
        "등급과 점수를 읽으세요. DD는 위험, AA는 최상. 등급은 마크 안, 숫자는 오른쪽. 재스캔 사이에 CVI를 한 단계 이상 올리세요."
    ),
    "Chiudi critical e warn; usa l’indice di criticità e il pack. Poi ripubblica e verifica.": (
        "치명·경고 항목을 닫고 심각도 지수와 팩을 쓰세요. 그런 다음 다시 게시하고 검증하세요."
    ),
    "Root del sito: %(path)s — oppure Edge + CMS connector.": (
        "사이트 루트: %(path)s — 또는 Edge + CMS 커넥터."
    ),
    "unico deliverable: logo originale in testa; apri e copia head / llms.txt / robots sul sito": (
        "단일 산출물: 상단에 원본 로고; 열어 head / llms.txt / robots를 사이트에 복사"
    ),
    "Plus · €19,99 Tasse escluse": "Plus · €19.99 세금 별도",
    "Business · €89,99 Tasse escluse": "Business · €89.99 세금 별도",
    "Metrica proprietaria Centropic: indice 0–100 con lettera DD→AA che sintetizza AIO+GEO (con penalità findings). In Panoramica il voto sta nel marchio; il punteggio numerico sta a destra. È lo standard da confrontare tra brand — non Domain Authority di terzi.": (
        "Centropic 고유 지표: AIO+GEO를 종합한 0–100 지수와 DD→AA 문자(Findings 감점 포함). "
        "개요에서 등급은 마크 안, 숫자는 오른쪽. 브랜드 비교 기준이며 제3자 Domain Authority가 아닙니다."
    ),
    "Score 0–100 dalla mix dei finding del run: (critici × 100 + warning × 40) / totale. In Panoramica sta sotto Distribuzione AIO, stessa colonna Crawl.": (
        "런 Findings 혼합의 0–100 점수: (치명 × 100 + 경고 × 40) / 전체. "
        "개요에서 AIO 분포 아래, 같은 크롤 열."
    ),
    "Le cinque pagine del prodotto: Panoramica, Benchmark, Prompt, Trend, Guida. Account e impostazioni restano nel menu avatar.": (
        "제품의 다섯 페이지: 개요, 벤치마크, 프롬프트, 트렌드, 가이드. 계정과 설정은 아바타 메뉴에 있습니다."
    ),
    "Insieme di artifact generati dall’analisi. Il file centropic-fix.html include il logo originale in testa, score, finding e snippet (llms, schema, meta, robots, checklist).": (
        "분석이 만든 산출물. centropic-fix.html 상단에 원본 로고와 점수, Findings, 스니펫(llms, schema, meta, robots, 체크리스트)이 있습니다."
    ),
    "Il workspace ha cinque pagine: Panoramica, Benchmark, Prompt, Trend, Guida.": (
        "워크스페이스에는 다섯 페이지가 있습니다: 개요, 벤치마크, 프롬프트, 트렌드, 가이드."
    ),
    "Workspace: CVI sul marchio, grafici AIO/GEO e pack in cinque pagine.": (
        "워크스페이스: 마크 위의 CVI, AIO/GEO 차트, 다섯 페이지의 팩."
    ),
    "Stato": "상태",
    "JSON-LD + FAQ + meta": "JSON-LD + FAQ + 메타",
    "API: GET /api/v1/sites/<id>/edge": "API: GET /api/v1/sites/<id>/edge",
    "Finding": "Finding",
    "Pack": "팩",
    "Quota operativa": "운영 쿼터",
    "Cosa misuriamo — e cosa no": "측정하는 것과 측정하지 않는 것",
    "Tre richieste frequenti in discovery restano fuori dal prodotto. Non per roadmap vuota: perché non le possiamo misurare in modo onesto, o perché brucerebbero la quota operativa senza rendere il sito più citabile.": (
        "영업 미팅에서 자주 나오는 세 가지 요청은 제품에 없습니다. "
        "로드맵이 비어서가 아닙니다. 정직하게 측정할 수 없거나, "
        "사이트를 더 잘 인용되게 만들지 못한 채 월 할당량만 태우기 때문입니다."
    ),
    "Attribution e ROI dalle citazioni LLM": "LLM 인용에 대한 기여도·ROI",
    "ChatGPT, Claude, Perplexity e Copilot non espongono impression, click o CTR. Un “ricavo generato dalla visibilità AI” sarebbe una correlazione inventata. Centropic misura le menzioni sul prompt bank (SoV Misurato) e, su Plus, può collegare Search Console come baseline di Search — non come traffico AI. Quando avremo sessioni con referrer AI dichiarati dal tuo analytics, le metteremo in Trend con l’etichetta Stimato.": (
        "ChatGPT, Claude, Perplexity, Copilot은 노출·클릭·CTR을 제공하지 않습니다. "
        "“AI 가시성으로 발생한 매출”은 지어낸 상관관계입니다. "
        "Centropic은 프롬프트 뱅크 기준으로 브랜드 언급을 측정하고(측정 SoV), "
        "Plus에서는 Search Console을 검색 기준선으로 연결할 수 있습니다. AI 트래픽이 아닙니다. "
        "분석 도구가 AI 리퍼러 세션을 알려 주면 Trend에 추정으로 표시합니다."
    ),
    "Simulazioni agente (buyer persona / funnel d’acquisto)": (
        "에이전트 시뮬레이션(구매 페르소나·구매 퍼널)"
    ),
    "Un journey multi-turno (CTO, procurement) moltiplica le probe LLM: un sim pieno può costare quanto 4–10 analisi Misurate e resta stocastico. Oggi il prompt bank su Plus accetta domande in stile buyer; non lanciamo agenti nel POST analyze perché svuoterebbero la quota mensile senza pubblicare un artifact. Se serve un report journey, è uno SKU a parte, non il default.": (
        "여러 턴의 여정(CTO, 구매)은 LLM 프로브를 몇 배로 늘립니다. "
        "전체 시뮬레이션 한 번은 측정 분석 4–10회 분량이고, 결과는 여전히 확률적입니다. "
        "Plus 프롬프트 뱅크는 이미 구매자 톤의 질문을 받습니다. "
        "POST /analyze에서 에이전트를 켜지 않는 이유는 월 할당량만 비우고 산출물을 내지 않기 때문입니다. "
        "여정 보고서가 필요하면 별도 SKU이지, 기본값이 아닙니다."
    ),
    "Audit nei dataset di pre-training (Common Crawl, Reddit, “pesi” GPT)": (
        "사전학습 데이터 감사(Common Crawl, Reddit, GPT ‘가중치’)"
    ),
    "Nessun modello chiuso certifica se il brand è nei suoi pesi. Dirlo in dashboard sarebbe un claim commerciale, non una misura. La GEO Suite già legge il tuo sito (grafo entità, sameAs, schema). Una presenza su Wikipedia/Wikidata è un finding utile; “sei nel training di ChatGPT” no. Restiamo su ciò che è osservabile.": (
        "비공개 모델은 브랜드가 가중치에 들어 있는지 증명하지 않습니다. "
        "대시보드에 쓰면 마케팅 주장이지 측정이 아닙니다. "
        "GEO Suite는 이미 사이트를 읽습니다(엔티티 그래프, sameAs, 스키마). "
        "위키피디아/위키데이터 존재는 유용한 파인딩이고, “ChatGPT 학습 데이터에 있다”는 그렇지 않습니다. "
        "관찰 가능한 것만 다룹니다."
    ),
    "Plus/Business: webhook pack.ready (checksum + URL Edge) così il CMS applica senza copiare i file": (
        "Plus/Business: pack.ready 웹훅(체크섬 + Edge URL). CMS가 파일을 복사하지 않고 pack을 적용합니다"
    ),
    "APPLY.md nello ZIP: evento pack.ready, idempotenza su signals_version": (
        "ZIP의 APPLY.md: pack.ready 이벤트, signals_version 기준 멱등"
    ),
    "GET /sites/<id> e /runs: AIO, GEO, CVI, SoV, criticità, checksum — OpenAPI in /api/v1/openapi.json": (
        "GET /sites/<id> 및 /runs: AIO, GEO, CVI, SoV, 심각도, 체크섬 — OpenAPI는 /api/v1/openapi.json"
    ),
    "Webhook analysis.completed + pack.ready (oltre agli alert di regressione)": (
        "analysis.completed 및 pack.ready 웹훅(회귀 알림 외에)"
    ),
    "Approfondimento su Misurato vs Stimato nella": "측정 vs 추정에 대한 자세한 내용은",
    "Eventi: analysis.completed, pack.ready (checksum + URL Edge, senza body dei file), analysis.alert (solo regressioni).": (
        "이벤트: analysis.completed, pack.ready(체크섬 + Edge URL, 파일 본문 없음), analysis.alert(회귀만)."
    ),
    "Firma HMAC in X-Centropic-Signature. Applica pack.ready una volta per idempotency_key.": (
        "HMAC은 X-Centropic-Signature에 있습니다. idempotency_key마다 pack.ready를 한 번만 적용하세요."
    ),
}

TABLES = {
    "en": EN,
    "de": DE,
    "es": ES,
    "zh_Hans": ZH,
    "ko": KO,
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
