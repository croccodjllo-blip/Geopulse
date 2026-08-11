# Centropic Edge Signals — Cloudflare Worker

Il nome pubblico corrente è **Centropic Signals**. Path primario esposto
dal Worker: `/centropic/signals.json`.

L'implementazione deployabile resta in
[`workers/geopulse-signals`](../geopulse-signals/) (Wrangler name storico
`geopulse-signals`, origin default `https://centropic.ai/e/…`) per non
interrompere deploy e route già installate.

- Path primario: `/centropic/signals.json`
- Alias legacy: `/geopulse/signals.json` → stesso upstream `/signals.json`
- Header risposta: `X-Centropic-Edge` (+ alias `X-GeoPulse-Edge`)
- Env: preferire `CENTROPIC_ORIGIN` (`GEOPULSE_ORIGIN` ancora accettato)

Per configurazione e deploy, segui il README della cartella di implementazione.
