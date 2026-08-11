"""Public evergreen GEO guides + methodology bodies (locale-aware)."""

from __future__ import annotations

from typing import Any

from flask_babel import gettext as _


def get_guide(slug: str) -> dict[str, Any] | None:
    """Return a translated guide dict for the active locale, or None."""
    builders = {
        "metodologia": _guide_metodologia,
        "llms-txt": _guide_llms_txt,
        "schema-ai": _guide_schema_ai,
        "score-vs-sov": _guide_score_vs_sov,
    }
    fn = builders.get(slug)
    return fn() if fn else None


# Backward-compatible mapping for imports that only need slug presence.
GUIDES = {
    "metodologia": {"path": "/metodologia"},
    "llms-txt": {"path": "/guide/llms-txt"},
    "schema-ai": {"path": "/guide/schema-ai"},
    "score-vs-sov": {"path": "/guide/score-vs-sov"},
}


def _guide_metodologia() -> dict[str, Any]:
    return {
        "path": "/metodologia",
        "eyebrow": _("Metodologia"),
        "title": _("Come Centropic misura il CVI"),
        "description": _(
            "Metodologia Centropic: Centropic Visibility Index (CVI), score AIO/GEO, badge Misurato/Stimato e citation share campionata."
        ),
        "lede": _(
            "L’IA non può citare ciò che non riesce a leggere. Centropic rende il brand visibile e interpretabile "
            "dai crawler generativi: chiudiamo gap di informazione e ambiguità entity prima che diventino allucinazioni."
        ),
        "body": _(
            """
  <section class="page-section">
    <h2 class="page-section__title">1. Centropic Visibility Index (CVI)</h2>
    <p class="lede">Il <strong>CVI</strong> è la metrica proprietaria di Centropic: un indice 0–100 con lettera <strong>DDD→AAA</strong> che sintetizza quanto il brand è predisposto a essere letto e citato dai sistemi generativi.</p>
    <p class="lede">Formula operativa: media di <strong>AIO</strong> (leggibilità) e <strong>GEO</strong> (citabilità), con penalità sui findings critical/warn. Non è un ranking pubblicitario né una garanzia di menzione: è lo standard Centropic per confrontare domini e nel tempo.</p>
    <p class="lede">Quando un marketer chiede <em>«qual è il tuo CVI?»</em> sta chiedendo questa predisposizione strutturale — non impression PR tradizionali.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">2. Cosa controlliamo (predisposizione strutturale)</h2>
    <p class="lede">Probe HTTP e parsing HTML sullo stesso dominio: title, meta, JSON-LD, FAQ, robots, llms.txt, sitemap, ai.txt, humans.txt, crawl multi-pagina. Questi finding possono essere badge <em>Misurato</em>.</p>
    <p class="lede">Centropic registra entity (Organization, sameAs, contatti), citabilità del copy e policy verso bot AI (GPTBot, ClaudeBot, PerplexityBot, Google-Extended) — il perimetro che i modelli devono poter leggere senza ambiguità.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">3. Score AIO / GEO (componenti del CVI)</h2>
    <p class="lede"><strong>AIO (AI-Driven Visibility)</strong> e <strong>GEO (Generative Engine Optimization)</strong> sono i due sotto-score 0–100 che alimentano il CVI: leggibilità per sistemi IA e citabilità / policy crawler.</p>
    <p class="lede">Il breakdown per engine (ChatGPT, Gemini, Claude, Perplexity, Grok, Azure AI) parte come <em>Stimato</em> sulla struttura osservata; su Plus/Business il citation monitor può aggiungere menzioni <em>Misurate</em>.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">4. Citation share (campione stocastico — Plus / Business)</h2>
    <p class="lede">Le risposte LLM sono stocastiche: non “Share of Voice” pubblicitaria (impression/PR), ma un <strong>campione di menzioni</strong> su prompt controllati. In prodotto resta l’etichetta SoV Misurato per continuità; metodologicamente è citation share campionata.</p>
    <ul class="plain-list">
      <li>Prompt personalizzabili in Impostazioni (prompt bank).</li>
      <li>Evidence badge <em>Misurato</em> per engine disponibili.</li>
      <li>Gemini e Azure AI sono proxy documentati (non Google AI Overview nativo né Copilot Bing nativo).</li>
    </ul>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">5. Trasparenza: la nostra promessa</h2>
    <ul class="plain-list">
      <li><strong>Garantiamo la predisposizione:</strong> brand e pagine rese leggibili, strutturate e raggiungibili dai crawler generativi — così l’IA ha materiale vero da citare, non vuoti da inventare.</li>
      <li>Il pack artifact è pronto per la pubblicazione; il go-live sul tuo stack resta sotto il tuo controllo (download, Edge o connector).</li>
      <li>Citation share measured è su <strong>Plus e Business</strong> (e Admin) con connector API attivi: misura campioni di menzione, non vende “posizione garantita” nelle UI di terzi.</li>
      <li>GEO in Centropic non significa GIS; AIO non significa All-in-One; CVI non è Domain Authority di terzi.</li>
    </ul>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">6. Approfondimenti</h2>
    <ul class="plain-list">
      <li><a href="/guida">Guida completa Centropic (servizi, analisi, glossario)</a></li>
      <li><a href="/guide/llms-txt">Guida llms.txt</a></li>
      <li><a href="/guide/schema-ai">Schema.org per answer engine</a></li>
      <li><a href="/guide/score-vs-sov">CVI, score AIO/GEO e citation share</a></li>
      <li><a href="/llms.txt">llms.txt pubblico di Centropic</a></li>
      <li><a href="/prodotto">Come funziona il prodotto</a></li>
    </ul>
  </section>
"""
        ),
    }


def _guide_llms_txt() -> dict[str, Any]:
    return {
        "path": "/guide/llms-txt",
        "eyebrow": _("Guida"),
        "title": _("llms.txt: guida pratica per la citabilità IA"),
        "description": _(
            "Cos’è llms.txt, come strutturarlo per AIO/GEO e come Centropic lo genera e lo valida nel crawl."
        ),
        "lede": _(
            "Un file root machine-readable che spiega brand, topic e pagine preferite ai modelli e crawler AI."
        ),
        "body": _(
            """
  <section class="page-section">
    <h2 class="page-section__title">Perché conta</h2>
    <p class="lede">llms.txt riduce ambiguità entity: dice chi sei, cosa offri e quali URL citare. In Centropic la presenza e la qualità del file alimentano score AIO/GEO (probe Misurato).</p>
    <p class="lede">Answer engine e crawler AI (GPTBot, ClaudeBot, PerplexityBot, Google-Extended) usano segnali pubblici; un llms.txt chiaro è un’ancora di citazione accanto a Schema.org e robots permissivi.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Sezioni utili</h2>
    <ul class="plain-list">
      <li>Site / Summary / Key topics con brand e dominio canonici</li>
      <li>Preferred citation (brand + acronimi espansi: AIO, GEO)</li>
      <li>Important pages con URL https assoluti</li>
      <li>Disambiguazione (cosa non siete: GIS, All-in-One generici)</li>
      <li>Contact e owner / parent organization</li>
    </ul>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Come Centropic aiuta</h2>
    <p class="lede">Ogni analisi genera una bozza <code>llms.txt</code> nel pack HTML unico. Pubblicala in root (<code>https://tuodominio/llms.txt</code>) e ri-analizza: il finding passa a “disponibile” se il probe la trova.</p>
    <p class="lede">Esempio vivo: il llms.txt di Centropic è su <a href="/llms.txt">centropic.ai/llms.txt</a>, con preferred citation e link a metodologia.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Checklist rapida</h2>
    <ul class="plain-list">
      <li>Una sola brand primaria (evita nomi fantasma)</li>
      <li>URL canonici https, niente query di tracking</li>
      <li>Allinea llms.txt a JSON-LD Organization e alla home</li>
      <li>Aggiorna la data quando cambi offerta o positioning</li>
    </ul>
    <p class="lede">Vedi anche <a href="/guide/schema-ai">Schema AI</a> e <a href="/metodologia">metodologia</a>.</p>
  </section>
"""
        ),
    }


def _guide_schema_ai() -> dict[str, Any]:
    return {
        "path": "/guide/schema-ai",
        "eyebrow": _("Guida"),
        "title": _("Schema.org per answer engine (AIO/GEO)"),
        "description": _(
            "Quali tipi Schema.org aiutano AI-Driven Visibility e Generative Engine Optimization: Organization, WebSite, FAQPage, SoftwareApplication, Article."
        ),
        "lede": _(
            "I dati strutturati non “garantiscono” citazioni, ma rendono l’entity leggibile a crawler e modelli. Aggiornato 30/07/2026."
        ),
        "body": _(
            """
  <section class="page-section">
    <h2 class="page-section__title">Tipi prioritari</h2>
    <ul class="plain-list">
      <li><strong>Organization</strong> + <strong>WebSite</strong> collegati via @id</li>
      <li><strong>FAQPage</strong> per Q&amp;A tipizzate allineate all’HTML visibile</li>
      <li><strong>SoftwareApplication</strong> o Product se vendi software (come Centropic)</li>
      <li><strong>Article</strong> / HowTo per guide evergreen con author e date</li>
    </ul>
    <p class="lede">Riferimento normativo: <a href="https://schema.org/" rel="noopener noreferrer" target="_blank">schema.org</a>. In Centropic i tipi rilevati alimentano score AIO/GEO (probe Misurato).</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Errori comuni</h2>
    <p class="lede">JSON-LD orfano senza tipi chiave, sameAs solo self-referenziali, FAQ senza acceptedAnswer, Organization senza contatto o logo. Centropic li segnala nei findings.</p>
    <p class="lede">Un sameAs verso il solo sito proprietario non basta: preferisci profili esterni reali (azienda madre, directory, social verificati).</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Checklist minima</h2>
    <ul class="plain-list">
      <li>name + url + email (o telephone) su Organization</li>
      <li>sameAs verso profili esterni reali (non pagine interne del sito)</li>
      <li>logo ImageObject con URL assoluto https e caption</li>
      <li>FAQPage solo se le domande sono visibili in pagina</li>
      <li>knowsAbout allineato a llms.txt e al copy della home</li>
    </ul>
    <p class="lede">Vedi anche <a href="/metodologia">metodologia</a>, <a href="/guide/llms-txt">llms.txt</a> e <a href="/guide/score-vs-sov">score vs SoV</a>.</p>
  </section>
"""
        ),
    }


def _guide_score_vs_sov() -> dict[str, Any]:
    return {
        "path": "/guide/score-vs-sov",
        "eyebrow": _("Guida"),
        "title": _("CVI, score AIO/GEO e citation share"),
        "description": _(
            "Centropic Visibility Index (CVI) vs sotto-score AIO/GEO e citation share campionata (SoV proxy/measured)."
        ),
        "lede": _(
            "Tre livelli: CVI (standard proprietario), AIO/GEO (componenti), citation share (campione stocastico sulle risposte)."
        ),
        "body": _(
            """
  <section class="page-section">
    <h2 class="page-section__title">Centropic Visibility Index (CVI)</h2>
    <p class="lede">Il <strong>CVI</strong> è la metrica di categoria di Centropic: 0–100 + lettera DDD→AAA. Riassume predisposizione strutturale (AIO+GEO) con penalità findings. È ciò che confronti tra brand, competitor e nel tempo.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Score AIO / GEO (componenti)</h2>
    <p class="lede">Sotto-score 0–100 da crawl e probe. Badge Stimato sul compositario; i check di presenza file possono essere Misurato.</p>
    <p class="lede"><strong>AIO (AI-Driven Visibility)</strong> premia leggibilità per sistemi IA: entity, schema, FAQ, llms.txt, meta. <strong>GEO (Generative Engine Optimization)</strong> premia citabilità e policy crawler AI.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Citation share (non SoV pubblicitaria)</h2>
    <p class="lede">Nei media tradizionali “Share of Voice” conta impression e PR. Qui misuriamo <strong>menzioni in risposte generative</strong> — stocastiche, prompt-dipendenti. In UI resta l’etichetta SoV per continuità; in metodologia è citation share.</p>
    <p class="lede"><strong>Proxy</strong>: formula su AIO/GEO + robots. <strong>Measured</strong> (Plus/Business): campioni prompt su LLM con conteggio menzioni brand. Non confondere i due.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Come leggerli insieme</h2>
    <p class="lede">Alza il <strong>CVI</strong> chiudendo i gap AIO/GEO: l’IA non cita ciò che non legge. Poi campiona la citation share. CVI alto = controllo del dato; measured = campione sulle risposte.</p>
    <p class="lede">Centropic mostra sempre l’evidence badge: Stimato, Misto o Misurato. Dettagli in <a href="/metodologia">metodologia</a> e nel prodotto su <a href="/prodotto">/prodotto</a>.</p>
  </section>
"""
        ),
    }
