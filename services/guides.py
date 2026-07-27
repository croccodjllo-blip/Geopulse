"""Public evergreen GEO guides + methodology bodies."""

from __future__ import annotations

GUIDES: dict[str, dict[str, str]] = {
    "metodologia": {
        "path": "/metodologia",
        "eyebrow": "Metodologia",
        "title": "Come GeoPulse misura AIO e GEO",
        "description": "Metodologia GeoPulse: score AIO/GEO da probe ed euristiche, badge Misurato/Stimato, limiti del SoV proxy e percorso verso SoV measured.",
        "lede": "Trasparenza sul metodo: cosa osserviamo sul sito, cosa stimiamo, cosa non promettiamo.",
        "body": """
  <section class="page-section">
    <h2 class="page-section__title">1. Cosa osserviamo (Misurato)</h2>
    <p class="lede">Probe HTTP e parsing HTML sullo stesso dominio: title, meta, JSON-LD, FAQ, robots, llms.txt, sitemap, ai.txt, humans.txt, crawl multi-pagina. Questi finding possono essere badge <em>Misurato</em>.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">2. Cosa stimiamo (Stimato / proxy)</h2>
    <p class="lede">Score compositi AIO/GEO, indice DDD→AAA e Share of Voice per engine derivano da formule euristiche sui segnali osservati. Non sono, di default, citazioni live su ChatGPT/Perplexity/Claude.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">3. Limiti</h2>
    <ul class="plain-list">
      <li>Nessuna garanzia di ranking o menzione da parte di modelli di terzi.</li>
      <li>Il pack artifact è una bozza operativa: la pubblicazione resta a carico del cliente.</li>
      <li>SoV measured (polling LLM) è disponibile solo se configurato e, tipicamente, su piano Plus.</li>
    </ul>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">4. Approfondimenti</h2>
    <ul class="plain-list">
      <li><a href="/guide/llms-txt">Guida llms.txt</a></li>
      <li><a href="/guide/schema-ai">Schema.org per answer engine</a></li>
      <li><a href="/guide/score-vs-sov">Score AIO/GEO vs Share of Voice</a></li>
    </ul>
  </section>
""",
    },
    "llms-txt": {
        "path": "/guide/llms-txt",
        "eyebrow": "Guida",
        "title": "llms.txt: guida pratica per la citabilità IA",
        "description": "Cos’è llms.txt, come strutturarlo per AIO/GEO e come GeoPulse lo genera e lo valida nel crawl.",
        "lede": "Un file root machine-readable che spiega brand, topic e pagine preferite ai modelli e crawler AI.",
        "body": """
  <section class="page-section">
    <h2 class="page-section__title">Perché conta</h2>
    <p class="lede">llms.txt riduce ambiguità entity: dice chi sei, cosa offri e quali URL citare. In GeoPulse la presenza e la qualità del file alimentano score AIO/GEO (probe Misurato).</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Sezioni utili</h2>
    <ul class="plain-list">
      <li>Site / Summary / Key topics</li>
      <li>Preferred citation (brand + acronimi espansi)</li>
      <li>Important pages con URL canonici https</li>
      <li>Contact</li>
    </ul>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Come GeoPulse aiuta</h2>
    <p class="lede">Ogni analisi genera una bozza <code>llms.txt</code> nel pack ZIP. Pubblicala in root e ri-analizza: il finding passa a “disponibile” se il probe la trova.</p>
  </section>
""",
    },
    "schema-ai": {
        "path": "/guide/schema-ai",
        "eyebrow": "Guida",
        "title": "Schema.org per answer engine (AIO/GEO)",
        "description": "Quali tipi Schema.org aiutano AI-Driven Visibility e Generative Engine Optimization: Organization, WebSite, FAQPage, SoftwareApplication, Article.",
        "lede": "I dati strutturati non “garantiscono” citazioni, ma rendono l’entity leggibile a crawler e modelli. Aggiornato 27/07/2026.",
        "body": """
  <section class="page-section">
    <h2 class="page-section__title">Tipi prioritari</h2>
    <ul class="plain-list">
      <li><strong>Organization</strong> + <strong>WebSite</strong> collegati via @id</li>
      <li><strong>FAQPage</strong> per Q&A tipizzate allineate all’HTML visibile</li>
      <li><strong>SoftwareApplication</strong> o Product se vendi software</li>
      <li><strong>Article</strong> / HowTo per guide evergreen con author e date</li>
    </ul>
    <p class="lede">Riferimento normativo: <a href="https://schema.org/" rel="noopener noreferrer" target="_blank">schema.org</a>. In GeoPulse i tipi rilevati alimentano score AIO/GEO (probe Misurato).</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Errori comuni</h2>
    <p class="lede">JSON-LD orfano senza tipi chiave, sameAs solo self-referenziali, FAQ senza acceptedAnswer, Organization senza contatto o logo. GeoPulse li segnala nei findings.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Checklist minima</h2>
    <ul class="plain-list">
      <li>name + url + email (o telephone) su Organization</li>
      <li>sameAs verso profili esterni reali (non pagine interne del sito)</li>
      <li>logo ImageObject con URL assoluto https</li>
      <li>FAQPage solo se le domande sono visibili in pagina</li>
    </ul>
    <p class="lede">Vedi anche <a href="/metodologia">metodologia</a> e <a href="/guide/llms-txt">llms.txt</a>.</p>
  </section>
""",
    },
    "score-vs-sov": {
        "path": "/guide/score-vs-sov",
        "eyebrow": "Guida",
        "title": "Score AIO/GEO vs Share of Voice",
        "description": "Differenza tra score AIO/GEO (diagnostica probe) e Share of Voice per answer engine (proxy o measured) in GeoPulse.",
        "lede": "Due metriche diverse: una valuta i segnali sul sito, l’altra stima la presenza relativa negli engine.",
        "body": """
  <section class="page-section">
    <h2 class="page-section__title">Score AIO / GEO</h2>
    <p class="lede">Indici 0–100 da crawl e probe. Badge Stimato sul compositario; singoli check di presenza file possono essere Misurato.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Share of Voice (SoV)</h2>
    <p class="lede"><strong>Proxy</strong>: formula su AIO/GEO + robots osservato. <strong>Measured</strong>: polling prompt su LLM (se abilitato) con conteggio menzioni brand. Non confondere i due.</p>
  </section>
  <section class="page-section">
    <h2 class="page-section__title">Come leggerli insieme</h2>
    <p class="lede">Alza prima i segnali (score), poi misura la voce (SoV). Un SoV alto con score basso è fragile; score alto senza SoV measured resta una diagnosi, non una prova di citazione.</p>
  </section>
""",
    },
}
