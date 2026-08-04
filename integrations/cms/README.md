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

## API

```http
GET /api/v1/sites/<id>/edge
Authorization: Bearer gp_…
```

Restituisce `edge_base`, `routes`, metadata adapter e URL dello ZIP.

```http
GET /api/v1/sites/<id>/edge/cms-bundle.zip
Authorization: Bearer gp_…
```

I generatori live sono in `services/cms_connector.py` — questa cartella documenta il contratto; non usare file statici con token di esempio in produzione.
