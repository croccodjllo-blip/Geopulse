# Centropic CMS Connector

Un solo contratto Edge Signals per ogni CMS / host: sul tuo dominio servono

- `/llms.txt`
- `/robots.txt` (Plus)
- `/.well-known/organization.jsonld` (Plus)
- `/geopulse/signals.json`

che fanno proxy verso `https://centropic.ai/e/<token>/…`.

## Installazione consigliata

1. Dashboard Centropic → **Attiva hosting dinamico** (Edge Signals).
2. Scarica **Connector CMS (.zip)** — contiene adapter già precompilati col tuo token.
3. Installa **un solo** adapter (WordPress *oppure* Drupal *oppure* rewrite host).

## Adapter inclusi nello ZIP

| Cartella | Piattaforma |
|----------|-------------|
| `wordpress/` | Plugin WordPress |
| `drupal/` | Modulo Drupal 10/11 |
| `shopify/` | Liquid + note proxy |
| `generic_php/` | PHP + Apache/Nginx |
| `netlify/` | `netlify.toml` / `_redirects` |
| `cloudflare/` | Worker |
| `vercel/` | `vercel.json` |
| `html_embed/` | Snippet `<head>` |

## Apply senza copy-paste

Dopo ogni analisi Plus/Business, se in Impostazioni è configurato un webhook HTTPS, Centropic invia:

- `analysis.completed` — score AIO/GEO/CVI, finding, checksum del pack
- `pack.ready` — `idempotency_key` `{site_id}:{signals_version}`, SHA-256 e URL Edge (nessun body dei file)

Firma: `X-Centropic-Signature` = HMAC-SHA256 del raw body. Applica una volta per chiave, poi `GET` gli endpoint Edge. Contratto nel file `APPLY.md` dello ZIP. Centropic non memorizza password CMS e non scrive sul tuo host.

## API

```http
GET /api/v1/sites/<id>
GET /api/v1/sites/<id>/runs
GET /api/v1/sites/<id>/edge
Authorization: Bearer ct_…
```

`GET /sites/<id>` restituisce metriche (AIO, GEO, CVI, SoV, criticità, checksum). Edge resta su `/edge`.

```http
GET /api/v1/sites/<id>/edge/cms-bundle.zip
Authorization: Bearer ct_…
```

Le chiavi legacy con prefisso `gp_` restano accettate per compatibilità.

I generatori live sono in `services/cms_connector.py` — questa cartella documenta il contratto; non usare file statici con token di esempio in produzione.
