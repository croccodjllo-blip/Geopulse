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
    "ChatGPT / Perplexity / Claude / Gemini (proxy AI Overview) / Grok / Azure AI (proxy Copilot): mention rate da prompt pack. Non equivale a ranking garantito nelle risposte live.": (
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
    "ChatGPT / Perplexity / Claude / Gemini (proxy AI Overview) / Grok / Azure AI (proxy Copilot): mention rate da prompt pack. Non equivale a ranking garantito nelle risposte live.": (
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
    "ChatGPT / Perplexity / Claude / Gemini (proxy AI Overview) / Grok / Azure AI (proxy Copilot): mention rate da prompt pack. Non equivale a ranking garantito nelle risposte live.": (
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
}
