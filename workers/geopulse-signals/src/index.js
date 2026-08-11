/**
 * Centropic Edge Signals — Cloudflare Worker
 *
 * Proxy llms.txt / robots.txt / signals.json / organization.jsonld
 * dal backend Centropic verso il dominio del cliente.
 *
 * Deploy path resta `workers/geopulse-signals/` per non rompere Wrangler
 * configs già installate. Nuove integrazioni: nome Centropic + path
 * `/centropic/signals.json` (alias legacy `/geopulse/signals.json`).
 *
 * Setup:
 *   1. Dashboard Centropic → Attiva Edge Signals → copia l'URL base /e/<token>
 *   2. Imposta CENTROPIC_ORIGIN (o legacy GEOPULSE_ORIGIN) via wrangler vars
 *   3. wrangler deploy
 *   4. Collega il Worker al dominio (Custom Domain / Route)
 */

const CENTROPIC_ORIGIN = "https://centropic.ai/e/REPLACE_TOKEN";
const SITE_ORIGIN = "https://example.com";

const ROUTES = {
  "/llms.txt": "/llms.txt",
  "/.well-known/llms.txt": "/llms.txt",
  "/robots.txt": "/robots.txt",
  "/.well-known/organization.jsonld": "/organization.jsonld",
  "/centropic/signals.json": "/signals.json",
  "/geopulse/signals.json": "/signals.json", // legacy alias
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = ROUTES[url.pathname];
    if (!path) {
      return new Response("Not found — Centropic Edge route missing", { status: 404 });
    }

    const origin = (
      env.CENTROPIC_ORIGIN ||
      env.GEOPULSE_ORIGIN ||
      CENTROPIC_ORIGIN
    ).replace(/\/$/, "");
    const upstream = origin + path;
    const headers = new Headers(request.headers);
    const siteOrigin = env.SITE_ORIGIN || SITE_ORIGIN;
    headers.set("X-Centropic-Site", siteOrigin);
    headers.set("X-GeoPulse-Site", siteOrigin); // legacy alias
    headers.set("Accept", "text/plain, application/json, */*");

    const res = await fetch(upstream, {
      headers,
      cf: { cacheTtl: 300, cacheEverything: true },
    });

    const out = new Headers(res.headers);
    out.set("Access-Control-Allow-Origin", "*");
    out.set("X-Centropic-Edge", "1");
    out.set("X-GeoPulse-Edge", "1"); // legacy alias
    out.set(
      "Cache-Control",
      "public, max-age=300, stale-while-revalidate=3600"
    );
    return new Response(res.body, { status: res.status, headers: out });
  },
};
