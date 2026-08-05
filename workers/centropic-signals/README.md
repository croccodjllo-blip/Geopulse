# Centropic Edge Signals — Cloudflare Worker

Il nome pubblico corrente è **Centropic Signals** e il percorso primario esposto
dal Worker è `/centropic/signals.json`.

L'implementazione deployabile resta temporaneamente in
[`workers/geopulse-signals`](../geopulse-signals/) per non interrompere deploy,
configurazioni Wrangler e route già installate. Il percorso
`/geopulse/signals.json` è supportato come alias legacy e punta allo stesso
payload `/signals.json`.

Per configurazione e deploy, segui il README della cartella legacy; per le nuove
integrazioni usa il nome Centropic e il percorso `/centropic/signals.json`.
