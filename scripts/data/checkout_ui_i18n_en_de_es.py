"""Native-quality UI/checkout/waiver i18n overlays (Italian msgid → locale).

Applied by scripts/upsert_checkout_ui_i18n.py.
Covers: digital waiver dialog, Plus checkout CTAs, empty catalog gaps,
trust/FAQ titles. Written as a native speaker would for B2B SaaS.
"""

from __future__ import annotations

# English (US) — concise product English
EN: dict[str, str] = {
    # Waiver dialog / checkout
    "Checkout": "Checkout",
    "Conferma obbligatoria prima del pagamento": "Required confirmation before payment",
    "Per aprire il checkout Paddle conferma l’erogazione immediata del servizio digitale. Vale anche se hai già un piano (rinnovo / aggiornamento metodo di pagamento).": (
        "To open Paddle checkout, confirm immediate delivery of the digital service. "
        "This also applies if you already have a plan (renewal / payment-method update)."
    ),
    "Chiedo l’erogazione immediata del servizio digitale (attivazione piano o accredito crediti) e riconosco di perdere il diritto di recesso di 14 giorni una volta iniziata l’erogazione, ai sensi della": (
        "I request immediate delivery of the digital service (plan activation or credit top-up) "
        "and acknowledge that I lose the 14-day withdrawal right once delivery begins, under the"
    ),
    "Politica di rimborso": "Refund Policy",
    "Spunta la casella per continuare.": "Check the box to continue.",
    "Continua al pagamento": "Continue to payment",
    "Annulla": "Cancel",
    "Obbligatorio per procedere al checkout.": "Required to proceed to checkout.",
    "Obbligatorio per aprire il checkout Paddle. Senza spunta, il pagamento non parte.": (
        "Required to open Paddle checkout. Without this checkbox, payment will not start."
    ),
    "Paga Plus · 14,99€/mese": "Pay Plus · €14.99/mo",
    "Apri checkout / aggiorna pagamento": "Open checkout / update payment",
    "Paga Business": "Pay Business",
    "Accedi e scegli Plus": "Sign in and choose Plus",
    "Prenota Plus": "Join Plus waitlist",
    "Apri DPA": "Open DPA",
    "Scarica DPA (.txt)": "Download DPA (.txt)",
    "Scarica DPA": "Download DPA",
    "Download .txt": "Download .txt",
    "Trust & security": "Trust & security",
    "Trust Centropic: sicurezza, sub-responsabili, retention, DPA Art. 28 e canali di supporto per procurement SaaS.": (
        "Centropic trust center: security, sub-processors, retention, Art. 28 DPA, and support channels for SaaS procurement."
    ),
    "FAQ Centropic": "Centropic FAQ",
    "Cookie Policy": "Cookie Policy",
    "Dichiarazione di accessibilità": "Accessibility statement",
    "Prodotto": "Product",
    # Empty catalog gaps
    "Analizzato": "Analyzed",
    "AIO/GEO sono sempre Stimato: predisposizione strutturale dal crawl. Il tab SoV mostra Misurato quando il citation monitor ha campionato gli engine (anche con 0 menzioni).": (
        "AIO/GEO are always Estimated: structural readiness from the crawl. The SoV tab shows Measured when the citation monitor has sampled the engines (even with 0 mentions)."
    ),
    "Sintesi score": "Score summary",
    "Citation share — probe Misurato eseguito": "Citation share — Measured probe completed",
    "Probe LLM eseguito: 0 menzioni su questo engine": "LLM probe completed: 0 mentions on this engine",
    "Misurato · 0": "Measured · 0",
    "Vai a": "Go to",
    "White-label": "White-label",
    "Se richiedi l’erogazione immediata del servizio (accesso al piano o accredito crediti) e riconosci di perdere il diritto di recesso una volta iniziata l’erogazione, il recesso non si applica dopo che il servizio è stato avviato. Il consenso è raccolto con checkbox esplicita prima del checkout Plus/crediti.": (
        "If you request immediate delivery of the service (plan access or credit top-up) and acknowledge "
        "that you lose the withdrawal right once delivery begins, withdrawal does not apply after the "
        "service has started. Consent is collected via an explicit checkbox before Plus/credit checkout."
    ),
    "Legale:": "Legal:",
    "Crawl, score e pack. Su Plus il SoV measured arriva in background dopo il report.": (
        "Crawl, score, and pack. On Plus, measured SoV arrives in the background after the report."
    ),
    "Stima: 30–90 secondi per crawl e pack": "Estimate: 30–90 seconds for crawl and pack",
    "Di solito 30–90 s. Il SoV measured Plus non blocca questa schermata.": (
        "Usually 30–90s. Plus measured SoV does not block this screen."
    ),
    "Avanzamento in tempo reale · report pronto dopo crawl/pack": (
        "Live progress · report ready after crawl/pack"
    ),
    "AIO/GEO e CVI allineati sul tuo brand e sui rivali del campione.": (
        "AIO/GEO and CVI aligned to your brand and the rivals in the sample."
    ),
    "Tu": "You",
    "Tua soglia": "Your threshold",
    "Il tuo brand": "Your brand",
    "Snapshot non disponibile": "Snapshot unavailable",
    "n/d": "n/a",
    "vs te": "vs you",
    "Rivale": "Rival",
    "Tuo AIO": "Your AIO",
    "Tuo GEO": "Your GEO",
    "ricevi un bonus quando attiva il piano Plus.": (
        "you get a bonus when they activate the Plus plan."
    ),
    "URL · crawl · score": "URL · crawl · score",
    "Dominio da analizzare": "Domain to analyze",
    "SoV measured in aggiornamento": "Measured SoV updating",
    "Il report Stimato è già pronto. Le citation Misurate arrivano in background (1–3 min) senza bloccare la dashboard.": (
        "The Estimated report is already ready. Measured citations arrive in the background (1–3 min) without blocking the dashboard."
    ),
    # Primary CTAs (native polish)
    "Analizza gratis": "Analyze for free",
    "Analizza il tuo sito": "Analyze your site",
    "Analizza il tuo dominio": "Analyze your domain",
    "Analizza un sito": "Analyze a site",
    "Inizia gratis": "Start for free",
    "Passa a Plus": "Upgrade to Plus",
    "Chiudi": "Close",
    "Continua": "Continue",
    "Apri dashboard": "Open dashboard",
}

# German (DE) — formal Sie, B2B SaaS
DE: dict[str, str] = {
    "Checkout": "Checkout",
    "Conferma obbligatoria prima del pagamento": "Erforderliche Bestätigung vor der Zahlung",
    "Per aprire il checkout Paddle conferma l’erogazione immediata del servizio digitale. Vale anche se hai già un piano (rinnovo / aggiornamento metodo di pagamento).": (
        "Um den Paddle-Checkout zu öffnen, bestätigen Sie die sofortige Erbringung des digitalen Dienstes. "
        "Das gilt auch, wenn Sie bereits einen Plan haben (Verlängerung / Aktualisierung der Zahlungsmethode)."
    ),
    "Chiedo l’erogazione immediata del servizio digitale (attivazione piano o accredito crediti) e riconosco di perdere il diritto di recesso di 14 giorni una volta iniziata l’erogazione, ai sensi della": (
        "Ich verlange die sofortige Erbringung des digitalen Dienstes (Planaktivierung oder Guthabenaufladung) "
        "und erkenne an, dass ich das 14-tägige Widerrufsrecht verliere, sobald die Erbringung beginnt, gemäß der"
    ),
    "Politica di rimborso": "Rückerstattungsrichtlinie",
    "Spunta la casella per continuare.": "Aktivieren Sie das Kontrollkästchen, um fortzufahren.",
    "Continua al pagamento": "Weiter zur Zahlung",
    "Annulla": "Abbrechen",
    "Obbligatorio per procedere al checkout.": "Erforderlich, um zum Checkout fortzufahren.",
    "Obbligatorio per aprire il checkout Paddle. Senza spunta, il pagamento non parte.": (
        "Erforderlich, um den Paddle-Checkout zu öffnen. Ohne Häkchen startet die Zahlung nicht."
    ),
    "Paga Plus · 14,99€/mese": "Plus bezahlen · 14,99 €/Monat",
    "Apri checkout / aggiorna pagamento": "Checkout öffnen / Zahlung aktualisieren",
    "Paga Business": "Business bezahlen",
    "Accedi e scegli Plus": "Anmelden und Plus wählen",
    "Prenota Plus": "Plus-Warteliste",
    "Apri DPA": "DPA öffnen",
    "Scarica DPA (.txt)": "DPA herunterladen (.txt)",
    "Scarica DPA": "DPA herunterladen",
    "Download .txt": "Download .txt",
    "Trust & security": "Trust & Security",
    "Trust Centropic: sicurezza, sub-responsabili, retention, DPA Art. 28 e canali di supporto per procurement SaaS.": (
        "Centropic Trust Center: Sicherheit, Unterauftragsverarbeiter, Aufbewahrung, Art.-28-DPA und Supportkanäle für SaaS-Procurement."
    ),
    "FAQ Centropic": "Centropic FAQ",
    "Cookie Policy": "Cookie-Richtlinie",
    "Dichiarazione di accessibilità": "Barrierefreiheitserklärung",
    "Prodotto": "Produkt",
    "Analizzato": "Analysiert",
    "AIO/GEO sono sempre Stimato: predisposizione strutturale dal crawl. Il tab SoV mostra Misurato quando il citation monitor ha campionato gli engine (anche con 0 menzioni).": (
        "AIO/GEO sind immer Geschätzt: strukturelle Bereitschaft aus dem Crawl. Der SoV-Tab zeigt Gemessen, "
        "wenn der Citation Monitor die Engines gesampelt hat (auch bei 0 Erwähnungen)."
    ),
    "Sintesi score": "Score-Übersicht",
    "Citation share — probe Misurato eseguito": "Citation Share — Gemessener Probe abgeschlossen",
    "Probe LLM eseguito: 0 menzioni su questo engine": "LLM-Probe abgeschlossen: 0 Erwähnungen auf dieser Engine",
    "Misurato · 0": "Gemessen · 0",
    "Vai a": "Gehe zu",
    "White-label": "White-Label",
    "Se richiedi l’erogazione immediata del servizio (accesso al piano o accredito crediti) e riconosci di perdere il diritto di recesso una volta iniziata l’erogazione, il recesso non si applica dopo che il servizio è stato avviato. Il consenso è raccolto con checkbox esplicita prima del checkout Plus/crediti.": (
        "Wenn Sie die sofortige Erbringung des Dienstes verlangen (Plan-Zugang oder Guthabenaufladung) und anerkennen, "
        "dass Sie das Widerrufsrecht mit Beginn der Erbringung verlieren, gilt der Widerruf nach Start des Dienstes nicht mehr. "
        "Die Zustimmung wird vor dem Plus-/Guthaben-Checkout per explizitem Kontrollkästchen eingeholt."
    ),
    "Legale:": "Rechtliches:",
    "Crawl, score e pack. Su Plus il SoV measured arriva in background dopo il report.": (
        "Crawl, Score und Pack. Bei Plus kommt der gemessene SoV nach dem Report im Hintergrund."
    ),
    "Stima: 30–90 secondi per crawl e pack": "Schätzung: 30–90 Sekunden für Crawl und Pack",
    "Di solito 30–90 s. Il SoV measured Plus non blocca questa schermata.": (
        "Meist 30–90 s. Der gemessene SoV bei Plus blockiert diesen Bildschirm nicht."
    ),
    "Avanzamento in tempo reale · report pronto dopo crawl/pack": (
        "Live-Fortschritt · Report bereit nach Crawl/Pack"
    ),
    "AIO/GEO e CVI allineati sul tuo brand e sui rivali del campione.": (
        "AIO/GEO und CVI ausgerichtet auf Ihre Marke und die Rivalen in der Stichprobe."
    ),
    "Tu": "Sie",
    "Tua soglia": "Ihre Schwelle",
    "Il tuo brand": "Ihre Marke",
    "Snapshot non disponibile": "Snapshot nicht verfügbar",
    "n/d": "k. A.",
    "vs te": "vs. Sie",
    "Rivale": "Rivale",
    "Tuo AIO": "Ihr AIO",
    "Tuo GEO": "Ihr GEO",
    "ricevi un bonus quando attiva il piano Plus.": (
        "erhalten Sie einen Bonus, wenn der Empfohlene den Plus-Plan aktiviert."
    ),
    "URL · crawl · score": "URL · Crawl · Score",
    "Dominio da analizzare": "Zu analysierende Domain",
    "SoV measured in aggiornamento": "Gemessener SoV wird aktualisiert",
    "Il report Stimato è già pronto. Le citation Misurate arrivano in background (1–3 min) senza bloccare la dashboard.": (
        "Der geschätzte Report ist bereits fertig. Gemessene Citations kommen im Hintergrund (1–3 Min.), ohne das Dashboard zu blockieren."
    ),
    # Primary CTAs (Sie / infinitive — B2B DE)
    "Analizza gratis": "Kostenlos analysieren",
    "Analizza il tuo sito": "Ihre Website analysieren",
    "Analizza il tuo dominio": "Ihre Domain analysieren",
    "Analizza un sito": "Eine Website analysieren",
    "Inizia gratis": "Kostenlos starten",
    "Passa a Plus": "Zu Plus wechseln",
    "Chiudi": "Schließen",
    "Continua": "Weiter",
    "Apri dashboard": "Dashboard öffnen",
}

# Spanish (ES) — Spain B2B, usted
ES: dict[str, str] = {
    "Checkout": "Checkout",
    "Conferma obbligatoria prima del pagamento": "Confirmación obligatoria antes del pago",
    "Per aprire il checkout Paddle conferma l’erogazione immediata del servizio digitale. Vale anche se hai già un piano (rinnovo / aggiornamento metodo di pagamento).": (
        "Para abrir el checkout de Paddle, confirme la prestación inmediata del servicio digital. "
        "También aplica si ya tiene un plan (renovación / actualización del método de pago)."
    ),
    "Chiedo l’erogazione immediata del servizio digitale (attivazione piano o accredito crediti) e riconosco di perdere il diritto di recesso di 14 giorni una volta iniziata l’erogazione, ai sensi della": (
        "Solicito la prestación inmediata del servicio digital (activación del plan o recarga de créditos) "
        "y reconozco que pierdo el derecho de desistimiento de 14 días una vez iniciada la prestación, conforme a la"
    ),
    "Politica di rimborso": "Política de reembolsos",
    "Spunta la casella per continuare.": "Marque la casilla para continuar.",
    "Continua al pagamento": "Continuar al pago",
    "Annulla": "Cancelar",
    "Obbligatorio per procedere al checkout.": "Obligatorio para continuar al checkout.",
    "Obbligatorio per aprire il checkout Paddle. Senza spunta, il pagamento non parte.": (
        "Obligatorio para abrir el checkout de Paddle. Sin la casilla, el pago no se inicia."
    ),
    "Paga Plus · 14,99€/mese": "Pagar Plus · 14,99 €/mes",
    "Apri checkout / aggiorna pagamento": "Abrir checkout / actualizar pago",
    "Paga Business": "Pagar Business",
    "Accedi e scegli Plus": "Inicie sesión y elija Plus",
    "Prenota Plus": "Lista de espera Plus",
    "Apri DPA": "Abrir DPA",
    "Scarica DPA (.txt)": "Descargar DPA (.txt)",
    "Scarica DPA": "Descargar DPA",
    "Download .txt": "Descargar .txt",
    "Trust & security": "Trust & security",
    "Trust Centropic: sicurezza, sub-responsabili, retention, DPA Art. 28 e canali di supporto per procurement SaaS.": (
        "Centro de confianza Centropic: seguridad, subencargados, retención, DPA art. 28 y canales de soporte para procurement SaaS."
    ),
    "FAQ Centropic": "FAQ de Centropic",
    "Cookie Policy": "Política de cookies",
    "Dichiarazione di accessibilità": "Declaración de accesibilidad",
    "Prodotto": "Producto",
    "Analizzato": "Analizado",
    "AIO/GEO sono sempre Stimato: predisposizione strutturale dal crawl. Il tab SoV mostra Misurato quando il citation monitor ha campionato gli engine (anche con 0 menzioni).": (
        "AIO/GEO son siempre Estimado: predisposición estructural del crawl. La pestaña SoV muestra Medido "
        "cuando el citation monitor ha muestreado los motores (incluso con 0 menciones)."
    ),
    "Sintesi score": "Resumen de score",
    "Citation share — probe Misurato eseguito": "Citation share — sonda Medida completada",
    "Probe LLM eseguito: 0 menzioni su questo engine": "Sonda LLM completada: 0 menciones en este motor",
    "Misurato · 0": "Medido · 0",
    "Vai a": "Ir a",
    "White-label": "White-label",
    "Se richiedi l’erogazione immediata del servizio (accesso al piano o accredito crediti) e riconosci di perdere il diritto di recesso una volta iniziata l’erogazione, il recesso non si applica dopo che il servizio è stato avviato. Il consenso è raccolto con checkbox esplicita prima del checkout Plus/crediti.": (
        "Si solicita la prestación inmediata del servicio (acceso al plan o recarga de créditos) y reconoce "
        "que pierde el derecho de desistimiento una vez iniciada la prestación, el desistimiento no aplica "
        "después de iniciado el servicio. El consentimiento se recoge con una casilla explícita antes del checkout Plus/créditos."
    ),
    "Legale:": "Legal:",
    "Crawl, score e pack. Su Plus il SoV measured arriva in background dopo il report.": (
        "Crawl, score y pack. En Plus, el SoV medido llega en segundo plano tras el informe."
    ),
    "Stima: 30–90 secondi per crawl e pack": "Estimación: 30–90 segundos para crawl y pack",
    "Di solito 30–90 s. Il SoV measured Plus non blocca questa schermata.": (
        "Suele ser 30–90 s. El SoV medido de Plus no bloquea esta pantalla."
    ),
    "Avanzamento in tempo reale · report pronto dopo crawl/pack": (
        "Progreso en tiempo real · informe listo tras crawl/pack"
    ),
    "AIO/GEO e CVI allineati sul tuo brand e sui rivali del campione.": (
        "AIO/GEO y CVI alineados con su marca y los rivales de la muestra."
    ),
    "Tu": "Usted",
    "Tua soglia": "Su umbral",
    "Il tuo brand": "Su marca",
    "Snapshot non disponibile": "Snapshot no disponible",
    "n/d": "n/d",
    "vs te": "vs usted",
    "Rivale": "Rival",
    "Tuo AIO": "Su AIO",
    "Tuo GEO": "Su GEO",
    "ricevi un bonus quando attiva il piano Plus.": (
        "recibe un bonus cuando active el plan Plus."
    ),
    "URL · crawl · score": "URL · crawl · score",
    "Dominio da analizzare": "Dominio a analizar",
    "SoV measured in aggiornamento": "SoV medido actualizándose",
    "Il report Stimato è già pronto. Le citation Misurate arrivano in background (1–3 min) senza bloccare la dashboard.": (
        "El informe Estimado ya está listo. Las citas Medidas llegan en segundo plano (1–3 min) sin bloquear el dashboard."
    ),
    # Primary CTAs
    "Analizza gratis": "Analizar gratis",
    "Analizza il tuo sito": "Analiza tu sitio",
    "Analizza il tuo dominio": "Analiza tu dominio",
    "Analizza un sito": "Analiza un sitio",
    "Inizia gratis": "Empieza gratis",
    "Passa a Plus": "Pasar a Plus",
    "Chiudi": "Cerrar",
    "Continua": "Continuar",
    "Apri dashboard": "Abrir dashboard",
}
