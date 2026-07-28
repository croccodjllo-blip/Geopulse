/**
 * GeoPulse Edge Signals — Cloudflare Worker
 *
 * Proxy llms.txt / robots.txt / signals.json / organization.jsonld
 * dal tuo endpoint GeoPulse verso il dominio del cliente.
 *
 * Setup:
 *   1. Dashboard GeoPulse → Attiva Edge Signals → copia l'URL base /e/<token>
 *   2. Imposta GEOPULSE_ORIGIN qui sotto (o via wrangler vars)
 *   3. wrangler deploy
 *   4. Collega il Worker al dominio (Custom Domain / Route)
 */

const GEOPULSE_ORIGIN = "https://geopulse.it/e/REPLACE_TOKEN";
const SITE_ORIGIN = "https://example.com";

const ROUTES = {
  "/llms.txt": "/llms.txt",
  "/.well-known/llms.txt": "/llms.txt",
  "/robots.txt": "/robots.txt",
  "/.well-known/organization.jsonld": "/organization.jsonld",
  "/geopulse/signals.json": "/signals.json",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = ROUTES[url.pathname];
    if (!path) {
      return new Response("Not found — GeoPulse Edge route missing", { status: 404 });
    }

    const origin = (env.GEOPULSE_ORIGIN || GEOPULSE_ORIGIN).replace(/\/$/, "");
    const upstream = origin + path;
    const headers = new Headers(request.headers);
    headers.set("X-GeoPulse-Site", env.SITE_ORIGIN || SITE_ORIGIN);
    headers.set("Accept", "text/plain, application/json, */*");

    const res = await fetch(upstream, {
      headers,
      cf: { cacheTtl: 300, cacheEverything: true },
    });

    const out = new Headers(res.headers);
    out.set("Access-Control-Allow-Origin", "*");
    out.set("X-GeoPulse-Edge", "1");
    out.set(
      "Cache-Control",
      "public, max-age=300, stale-while-revalidate=3600"
    );
    return new Response(res.body, { status: res.status, headers: out });
  },
};
