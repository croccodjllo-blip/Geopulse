# GeoPulse Edge Signals — Cloudflare Worker

Proxy dinamico degli artifact AIO/GEO (`llms.txt`, `robots.txt`, `signals.json`, JSON-LD)
dal backend GeoPulse verso il dominio del cliente.

## Perché

Uno ZIP statico diventa obsoleto quando cambiano i crawler IA.
Con Edge Signals la policy `robots.txt` e il manifest `signals.json` restano
allineati alla lista crawler mantenuta da GeoPulse — lock-in infrastrutturale.

## Deploy

1. In dashboard GeoPulse: **Attiva hosting dinamico** e copia l'URL `/e/<token>`.
2. Modifica `wrangler.toml` / `src/index.js`:
   - `GEOPULSE_ORIGIN` = `https://geopulse.it/e/<token>`
   - `SITE_ORIGIN` = il tuo sito
3. `npx wrangler deploy`
4. Collega una route sul dominio (es. `example.com/llms.txt`, `example.com/robots.txt`).

## Vercel

Usa lo snippet `vercel.json` dalla dashboard (rewrite verso gli stessi endpoint).

## Piano

- **Free**: `llms.txt` + `signals.json` hostati
- **Plus**: + `robots.txt` live, `organization.jsonld`, snippet Worker/Vercel
