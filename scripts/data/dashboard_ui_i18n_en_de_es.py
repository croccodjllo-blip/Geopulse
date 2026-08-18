"""Native dashboard UI i18n — EN / DE / ES (Italian msgid → locale)."""

from __future__ import annotations

# English (US) — concise product English
EN: dict[str, str] = {
    "Avvia": "Start",
    "Salva": "Save",
    "Salva alert": "Save alerts",
    "Salva prompt bank": "Save prompt bank",
    "Salva white-label": "Save white-label",
    "Salva nuova password": "Save new password",
    "Aggiorna password": "Update password",
    "Disattivato": "Off",
    "Ogni giorno": "Every day",
    "Ogni settimana": "Every week",
    "Frequenza re-scan": "Rescan frequency",
    "Frequenza": "Frequency",
    "Orario (UTC)": "Time (UTC)",
    "Email alert su regressioni": "Email alerts on regressions",
    "Prompt bank (un prompt per riga)": "Prompt bank (one prompt per line)",
    "Applica pack al prompt bank": "Apply pack to prompt bank",
    "— seleziona —": "— select —",
    "Brand agenzia": "Agency brand",
    "Colore primario": "Primary color",
    "Nota piè di pagina": "Footer note",
    "URL del sito": "Site URL",
    "Competitor (max 3 URL, uno per riga)": "Competitors (max 3 URLs, one per line)",
    "Deep crawl (Plus: più pagine, più lento)": "Deep crawl (Plus: more pages, slower)",
    "Analisi dominio %(host)s: %(n)s pagine · suite AIO/GEO completa.": (
        "Domain analysis %(host)s: %(n)s pages · full AIO/GEO suite."
    ),
    "Analisi di %(host)s: suite AIO/GEO completa (content, brand, GEO, tecnico, llms/robots).": (
        "Analysis of %(host)s: full AIO/GEO suite (content, brand, GEO, technical, llms/robots)."
    ),
    "ChatGPT / Perplexity / Claude / Gemini API / Grok / Azure OpenAI: mention rate da prompt pack. Non è AI Overview o Copilot nativo, né ranking garantito nelle risposte live.": (
        "ChatGPT / Perplexity / Claude / Gemini (AI Overview proxy) / Grok / "
        "Azure AI (Copilot proxy): mention rate from the prompt pack. "
        "Not a guaranteed ranking in live answers."
    ),
    "Monitoraggio": "Monitoring",
    "Prossimo:": "Next:",
    "Ultimo": "Last",
    "Schedule attivo, in coda al worker.": "Schedule active, queued for the worker.",
    "Scegli frequenza e orario, poi salva. Il worker Plus/Business esegue i controlli in automatico.": (
        "Choose frequency and time, then save. The Plus/Business worker runs checks automatically."
    ),
    "Misurato (multi-engine probe)": "Measured (multi-engine probe)",
    "Non disponibile": "Unavailable",
    "SoV Misurato in corso": "Measured SoV in progress",
    "SoV Misurato in coda": "Measured SoV queued",
    "SoV Misurato in corso: stiamo campionando le citazioni sugli engine. Intanto vedi solo la stima strutturale.": (
        "Measured SoV in progress: we're sampling citations across engines. "
        "For now you only see the structural estimate."
    ),
    "SoV Misurato in coda: i probe LLM partono a breve. Intanto vedi solo la stima strutturale.": (
        "Measured SoV queued: LLM probes start shortly. "
        "For now you only see the structural estimate."
    ),
    "SoV Misurato in attesa di coda o budget. Finché i probe non completano, vedi solo la stima strutturale — non è ancora una misurazione live.": (
        "Measured SoV is waiting on queue or daily budget. Until probes finish, "
        "you only see the structural estimate — not a live measurement yet."
    ),
    "Il report Stimato è già pronto. I probe LLM stanno misurando le citazioni in background (1–3 min): i valori Misurati aggiornano questa vista a job completato.": (
        "The Estimated report is already ready. LLM probes are measuring citations "
        "in the background (1–3 min): Measured values refresh this view when the job finishes."
    ),
    # SoV panel titles (native product English)
    "Ripartizione per engine IA": "AI engine breakdown",
    "Citation share": "Citation share",
    "Citation share — Misurato · 0 menzioni": "Citation share — Measured · 0 mentions",
    "Citation share — Misurato 0 menzioni": "Citation share — Measured · 0 mentions",
    "Citation share (stimata · readiness)": "Citation share (estimated · readiness)",
    "Citation share brand": "Brand citation share",
    "AI Engine Breakdown": "AI engine breakdown",
}

# German (DE) — formal Sie / infinitive CTAs
DE: dict[str, str] = {
    "Avvia": "Starten",
    "Salva": "Speichern",
    "Salva alert": "Alerts speichern",
    "Salva prompt bank": "Prompt-Bank speichern",
    "Salva white-label": "White-Label speichern",
    "Salva nuova password": "Neues Passwort speichern",
    "Aggiorna password": "Passwort aktualisieren",
    "Disattivato": "Aus",
    "Ogni giorno": "Täglich",
    "Ogni settimana": "Wöchentlich",
    "Frequenza re-scan": "Rescan-Frequenz",
    "Frequenza": "Frequenz",
    "Orario (UTC)": "Uhrzeit (UTC)",
    "Email alert su regressioni": "E-Mail-Alerts bei Regressionen",
    "Prompt bank (un prompt per riga)": "Prompt-Bank (ein Prompt pro Zeile)",
    "Applica pack al prompt bank": "Pack auf Prompt-Bank anwenden",
    "— seleziona —": "— auswählen —",
    "Brand agenzia": "Agenturmarke",
    "Colore primario": "Primärfarbe",
    "Nota piè di pagina": "Fußzeilenhinweis",
    "URL del sito": "Website-URL",
    "Competitor (max 3 URL, uno per riga)": "Wettbewerber (max. 3 URLs, eine pro Zeile)",
    "Deep crawl (Plus: più pagine, più lento)": "Deep Crawl (Plus: mehr Seiten, langsamer)",
    "Analisi dominio %(host)s: %(n)s pagine · suite AIO/GEO completa.": (
        "Domainanalyse %(host)s: %(n)s Seiten · vollständige AIO/GEO-Suite."
    ),
    "Analisi di %(host)s: suite AIO/GEO completa (content, brand, GEO, tecnico, llms/robots).": (
        "Analyse von %(host)s: vollständige AIO/GEO-Suite (Content, Brand, GEO, Technik, llms/robots)."
    ),
    "ChatGPT / Perplexity / Claude / Gemini API / Grok / Azure OpenAI: mention rate da prompt pack. Non è AI Overview o Copilot nativo, né ranking garantito nelle risposte live.": (
        "ChatGPT / Perplexity / Claude / Gemini (AI-Overview-Proxy) / Grok / "
        "Azure AI (Copilot-Proxy): Mention-Rate aus dem Prompt-Pack. "
        "Kein garantiertes Ranking in Live-Antworten."
    ),
    "Monitoraggio": "Monitoring",
    "Prossimo:": "Nächster:",
    "Ultimo": "Letzter",
    "Schedule attivo, in coda al worker.": "Zeitplan aktiv, in der Worker-Warteschlange.",
    "Scegli frequenza e orario, poi salva. Il worker Plus/Business esegue i controlli in automatico.": (
        "Frequenz und Uhrzeit wählen, dann speichern. Der Plus-/Business-Worker führt die Checks automatisch aus."
    ),
    "Misurato (multi-engine probe)": "Gemessen (Multi-Engine-Probe)",
    "Non disponibile": "Nicht verfügbar",
    "SoV Misurato in corso": "Gemessenes SoV läuft",
    "SoV Misurato in coda": "Gemessenes SoV in Warteschlange",
    "SoV Misurato in corso: stiamo campionando le citazioni sugli engine. Intanto vedi solo la stima strutturale.": (
        "Gemessenes SoV läuft: Wir sampeln Zitationen über die Engines. "
        "Bis dahin sehen Sie nur die strukturelle Schätzung."
    ),
    "SoV Misurato in coda: i probe LLM partono a breve. Intanto vedi solo la stima strutturale.": (
        "Gemessenes SoV in Warteschlange: LLM-Probes starten in Kürze. "
        "Bis dahin sehen Sie nur die strukturelle Schätzung."
    ),
    "SoV Misurato in attesa di coda o budget. Finché i probe non completano, vedi solo la stima strutturale — non è ancora una misurazione live.": (
        "Gemessenes SoV wartet auf Warteschlange oder Tagesbudget. Bis die Probes "
        "fertig sind, sehen Sie nur die strukturelle Schätzung — noch keine Live-Messung."
    ),
    "Il report Stimato è già pronto. I probe LLM stanno misurando le citazioni in background (1–3 min): i valori Misurati aggiornano questa vista a job completato.": (
        "Der geschätzte Report ist bereits fertig. LLM-Probes messen Zitationen "
        "im Hintergrund (1–3 Min.): Gemessene Werte aktualisieren diese Ansicht nach Jobende."
    ),
    # SoV-Panel-Titel (native DE)
    "Ripartizione per engine IA": "Aufschlüsselung nach AI-Engine",
    "Citation share": "Citation Share",
    "Citation share — Misurato · 0 menzioni": "Citation Share — Gemessen · 0 Erwähnungen",
    "Citation share — Misurato 0 menzioni": "Citation Share — Gemessen · 0 Erwähnungen",
    "Citation share (stimata · readiness)": "Citation Share (geschätzt · Readiness)",
    "Citation share brand": "Marken-Citation-Share",
    "AI Engine Breakdown": "Aufschlüsselung nach AI-Engine",
}

# Spanish (ES) — Spain B2B
ES: dict[str, str] = {
    "Avvia": "Iniciar",
    "Salva": "Guardar",
    "Salva alert": "Guardar alertas",
    "Salva prompt bank": "Guardar prompt bank",
    "Salva white-label": "Guardar white-label",
    "Salva nuova password": "Guardar nueva contraseña",
    "Aggiorna password": "Actualizar contraseña",
    "Disattivato": "Desactivado",
    "Ogni giorno": "Cada día",
    "Ogni settimana": "Cada semana",
    "Frequenza re-scan": "Frecuencia de re-scan",
    "Frequenza": "Frecuencia",
    "Orario (UTC)": "Hora (UTC)",
    "Email alert su regressioni": "Alertas por email ante regresiones",
    "Prompt bank (un prompt per riga)": "Prompt bank (un prompt por línea)",
    "Applica pack al prompt bank": "Aplicar pack al prompt bank",
    "— seleziona —": "— seleccione —",
    "Brand agenzia": "Marca de agencia",
    "Colore primario": "Color primario",
    "Nota piè di pagina": "Nota de pie de página",
    "URL del sito": "URL del sitio",
    "Competitor (max 3 URL, uno per riga)": "Competidores (máx. 3 URL, una por línea)",
    "Deep crawl (Plus: più pagine, più lento)": "Deep crawl (Plus: más páginas, más lento)",
    "Analisi dominio %(host)s: %(n)s pagine · suite AIO/GEO completa.": (
        "Análisis del dominio %(host)s: %(n)s páginas · suite AIO/GEO completa."
    ),
    "Analisi di %(host)s: suite AIO/GEO completa (content, brand, GEO, tecnico, llms/robots).": (
        "Análisis de %(host)s: suite AIO/GEO completa (contenido, marca, GEO, técnico, llms/robots)."
    ),
    "ChatGPT / Perplexity / Claude / Gemini API / Grok / Azure OpenAI: mention rate da prompt pack. Non è AI Overview o Copilot nativo, né ranking garantito nelle risposte live.": (
        "ChatGPT / Perplexity / Claude / Gemini (proxy AI Overview) / Grok / "
        "Azure AI (proxy Copilot): tasa de mención del prompt pack. "
        "No equivale a un ranking garantizado en respuestas en vivo."
    ),
    "Monitoraggio": "Monitorización",
    "Prossimo:": "Próximo:",
    "Ultimo": "Último",
    "Schedule attivo, in coda al worker.": "Programación activa, en cola del worker.",
    "Scegli frequenza e orario, poi salva. Il worker Plus/Business esegue i controlli in automatico.": (
        "Elija frecuencia y hora, luego guarde. El worker Plus/Business ejecuta los controles automáticamente."
    ),
    "Misurato (multi-engine probe)": "Medido (sonda multi-motor)",
    "Non disponibile": "No disponible",
    "SoV Misurato in corso": "SoV Medido en curso",
    "SoV Misurato in coda": "SoV Medido en cola",
    "SoV Misurato in corso: stiamo campionando le citazioni sugli engine. Intanto vedi solo la stima strutturale.": (
        "SoV Medido en curso: estamos muestreando citas en los motores. "
        "Por ahora solo ve la estimación estructural."
    ),
    "SoV Misurato in coda: i probe LLM partono a breve. Intanto vedi solo la stima strutturale.": (
        "SoV Medido en cola: las sondas LLM arrancan en breve. "
        "Por ahora solo ve la estimación estructural."
    ),
    "SoV Misurato in attesa di coda o budget. Finché i probe non completano, vedi solo la stima strutturale — non è ancora una misurazione live.": (
        "SoV Medido en espera de cola o presupuesto. Hasta que las sondas terminen, "
        "solo ve la estimación estructural — aún no es una medición en vivo."
    ),
    "Il report Stimato è già pronto. I probe LLM stanno misurando le citazioni in background (1–3 min): i valori Misurati aggiornano questa vista a job completato.": (
        "El informe Estimado ya está listo. Las sondas LLM miden citas en segundo "
        "plano (1–3 min): los valores Medidos actualizan esta vista al completar el job."
    ),
    # Títulos del panel SoV (ES nativo)
    "Ripartizione per engine IA": "Desglose por motor de IA",
    "Citation share": "Cuota de citas",
    "Citation share — Misurato · 0 menzioni": "Cuota de citas — Medido · 0 menciones",
    "Citation share — Misurato 0 menzioni": "Cuota de citas — Medido · 0 menciones",
    "Citation share (stimata · readiness)": "Cuota de citas (estimada · readiness)",
    "Citation share brand": "Cuota de citas de la marca",
    "AI Engine Breakdown": "Desglose por motor de IA",
}
