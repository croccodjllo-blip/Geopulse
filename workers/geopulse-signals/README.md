# Centropic Edge Signals — Cloudflare Worker

Proxy dinamico degli artifact AIO/GEO (`llms.txt`, `robots.txt`, `signals.json`, JSON-LD)
dal backend Centropic verso il dominio del cliente.

> Cartella storica: `workers/geopulse-signals/` (nome Wrangler invariato per
> non rompere deploy esistenti). Docs pubbliche e nuove integrazioni usano
> il nome **Centropic Signals** (`workers/centropic-signals/`).

## Perché

Uno ZIP statico diventa obsoleto quando cambiano i crawler IA.
Con Edge Signals la policy `robots.txt` e il manifest `signals.json` restano
allineati alla lista crawler mantenuta da Centropic.

## Deploy

1. In dashboard Centropic: **Attiva hosting dinamico** e copia l'URL `/e/<token>`.
2. Modifica `wrangler.toml` / vars:
   - `CENTROPIC_ORIGIN` = `https://centropic.ai/e/<token>`
   - (`GEOPULSE_ORIGIN` resta accettato come alias legacy)
   - `SITE_ORIGIN` = il tuo sito
3. `npx wrangler deploy`
4. Collega una route sul dominio (es. `example.com/llms.txt`, `example.com/robots.txt`,
   `example.com/centropic/signals.json`).

Path supportati:

| Path Worker | Upstream |
|---|---|
| `/llms.txt` | `/llms.txt` |
| `/robots.txt` | `/robots.txt` |
| `/centropic/signals.json` | `/signals.json` |
| `/geopulse/signals.json` | `/signals.json` (legacy) |
| `/.well-known/organization.jsonld` | `/organization.jsonld` |

## Vercel

Usa lo snippet `vercel.json` dalla dashboard (rewrite verso gli stessi endpoint).

## Piano

- **Free**: `llms.txt` + `signals.json` hostati
- **Plus / Business**: + `robots.txt` live, `organization.jsonld`, snippet Worker/Vercel
