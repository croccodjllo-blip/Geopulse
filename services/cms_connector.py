"""Universal CMS connector for Centropic Edge Signals.

One contract for every CMS: rewrite/proxy well-known AIO paths to
``https://centropic.ai/e/<token>/…``. Native plugins (WordPress, Drupal)
and static configs (Shopify, Nginx, Apache, Netlify) share the same map.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

from services.edge_signals import (
    cloudflare_worker_snippet,
    edge_base_url,
    html_embed_snippet,
    vercel_edge_config_snippet,
)

# Paths exposed on the customer domain → Edge upstream suffix.
EDGE_ROUTE_MAP: dict[str, str] = {
    "/llms.txt": "/llms.txt",
    "/.well-known/llms.txt": "/llms.txt",
    "/robots.txt": "/robots.txt",
    "/.well-known/organization.jsonld": "/organization.jsonld",
    "/geopulse/signals.json": "/signals.json",
    "/centropic/signals.json": "/signals.json",
}


def build_cms_bundle(
    *,
    origin_edge_base: str,
    site_origin: str,
    public_base: str = "https://centropic.ai",
) -> dict[str, Any]:
    """Return install artifacts for all supported CMS / hosts."""
    base = origin_edge_base.rstrip("/")
    site = site_origin.rstrip("/")
    signals_url = f"{base}/signals.json"
    return {
        "schema": "centropic.cms_connector/v1",
        "edge_base": base,
        "site_origin": site,
        "routes": dict(EDGE_ROUTE_MAP),
        "docs": f"{public_base.rstrip('/')}/faq#edge-signals",
        "adapters": {
            "wordpress": {
                "label": "WordPress",
                "files": {
                    "centropic-edge/centropic-edge.php": _wordpress_plugin_main(
                        edge_base=base, site_origin=site
                    ),
                    "centropic-edge/readme.txt": _wordpress_readme(),
                },
                "install": (
                    "Carica la cartella centropic-edge in wp-content/plugins/, "
                    "attiva il plugin e salva l'URL Edge in Impostazioni → Centropic Edge."
                ),
            },
            "shopify": {
                "label": "Shopify",
                "files": {
                    "snippets/centropic-edge.liquid": _shopify_liquid(edge_base=base),
                    "README.md": _shopify_readme(edge_base=base),
                },
                "install": (
                    "Inserisci lo snippet nel theme layout e configura un app proxy "
                    "o Cloudflare Worker per /llms.txt e /robots.txt."
                ),
            },
            "drupal": {
                "label": "Drupal",
                "files": {
                    "centropic_edge/centropic_edge.info.yml": _drupal_info(),
                    "centropic_edge/centropic_edge.module": _drupal_module(),
                    "centropic_edge/centropic_edge.routing.yml": _drupal_routing(),
                    "centropic_edge/src/Controller/EdgeProxyController.php": _drupal_controller(
                        edge_base=base
                    ),
                    "centropic_edge/README.md": _drupal_readme(edge_base=base),
                },
                "install": (
                    "Copia centropic_edge in modules/custom/, abilita il modulo "
                    "e imposta centropic_edge.settings.edge_base."
                ),
            },
            "generic_php": {
                "label": "PHP generico (Joomla, Prestashop, custom)",
                "files": {
                    "centropic-proxy.php": _generic_php_proxy(edge_base=base),
                    ".htaccess.centropic": _apache_htaccess(),
                    "nginx-centropic.conf": _nginx_conf(edge_base=base),
                    "README.md": _generic_php_readme(edge_base=base),
                },
                "install": (
                    "Metti centropic-proxy.php in document root e punta i path "
                    "AIO allo script (Apache/Nginx sample inclusi)."
                ),
            },
            "netlify": {
                "label": "Netlify",
                "files": {
                    "netlify.toml": _netlify_toml(edge_base=base),
                    "_redirects": _netlify_redirects(edge_base=base),
                },
                "install": "Committa netlify.toml (o _redirects) e fai redeploy.",
            },
            "cloudflare": {
                "label": "Cloudflare Worker",
                "files": {
                    "worker.js": cloudflare_worker_snippet(
                        origin_edge_base=base, site_origin=site
                    ),
                },
                "install": "Deploy con wrangler; collega le route sul dominio.",
            },
            "vercel": {
                "label": "Vercel",
                "files": {
                    "vercel.json": vercel_edge_config_snippet(origin_edge_base=base),
                },
                "install": "Committa vercel.json nella root del progetto.",
            },
            "html_embed": {
                "label": "HTML / Webflow / Framer / qualsiasi CMS",
                "files": {
                    "embed.html": html_embed_snippet(signals_url=signals_url),
                },
                "install": (
                    "Incolla embed.html nel <head>. Per llms.txt/robots sul dominio "
                    "usa Worker, rewrite host o plugin nativo."
                ),
            },
        },
    }


def cms_bundle_zip_bytes(
    *,
    origin_edge_base: str,
    site_origin: str,
    public_base: str = "https://centropic.ai",
) -> bytes:
    """ZIP with every adapter ready to drop into a CMS / host."""
    bundle = build_cms_bundle(
        origin_edge_base=origin_edge_base,
        site_origin=site_origin,
        public_base=public_base,
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README.md",
            _root_readme(
                edge_base=bundle["edge_base"],
                site_origin=bundle["site_origin"],
                docs=bundle["docs"],
            ),
        )
        zf.writestr("routes.json", _pretty_json(bundle["routes"]))
        for key, adapter in bundle["adapters"].items():
            for rel, content in (adapter.get("files") or {}).items():
                zf.writestr(f"{key}/{rel}", content)
            zf.writestr(f"{key}/INSTALL.txt", adapter.get("install") or "")
    return buf.getvalue()


def edge_context_for_site(
    *,
    public_base: str,
    token: str,
    site_url: str,
) -> dict[str, str]:
    base = edge_base_url(public_base, token)
    return {
        "edge_base": base,
        "site_origin": (site_url or "").rstrip("/") or "https://example.com",
        "llms_url": f"{base}/llms.txt",
        "signals_url": f"{base}/signals.json",
        "robots_url": f"{base}/robots.txt",
        "jsonld_url": f"{base}/organization.jsonld",
    }


# ── file generators ──────────────────────────────────────────────────────────


def _pretty_json(obj: Any) -> str:
    import json

    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def _root_readme(*, edge_base: str, site_origin: str, docs: str) -> str:
    return f"""# Centropic CMS Connector

Universal Edge Signals installer for any CMS / host.

- Edge base: `{edge_base}`
- Site: `{site_origin}`
- Docs: {docs}

## What it does

Proxies these paths on your domain to Centropic (live crawler policy):

- `/llms.txt`
- `/robots.txt` (Plus)
- `/.well-known/organization.jsonld` (Plus)
- `/geopulse/signals.json`

## Pick your adapter

| Folder | Platform |
|--------|----------|
| `wordpress/` | WordPress plugin |
| `shopify/` | Theme Liquid + proxy notes |
| `drupal/` | Drupal 10 module |
| `generic_php/` | Any PHP site + Apache/Nginx |
| `netlify/` | Netlify redirects |
| `cloudflare/` | Worker |
| `vercel/` | vercel.json rewrites |
| `html_embed/` | Head snippet for any builder |

Activate Edge Signals in the Centropic dashboard first, then deploy one adapter.
"""


def _wordpress_plugin_main(*, edge_base: str, site_origin: str) -> str:
    # Keep plugin bootstrap self-contained; default option = this edge base.
    return f"""<?php
/**
 * Plugin Name: Centropic Edge Signals
 * Description: Proxies llms.txt, robots.txt and AI signals from Centropic Edge to your WordPress site (works with any theme / page builder).
 * Version: 1.0.0
 * Author: Centropic
 * License: GPL-2.0-or-later
 * Text Domain: centropic-edge
 */

if (!defined('ABSPATH')) {{
    exit;
}}

define('CENTROPIC_EDGE_VERSION', '1.0.0');
define('CENTROPIC_EDGE_DEFAULT', '{edge_base}');

final class Centropic_Edge_Plugin {{
    const OPTION = 'centropic_edge_base';

    public static function init(): void {{
        add_action('init', [__CLASS__, 'add_rewrites']);
        add_filter('query_vars', [__CLASS__, 'query_vars']);
        add_action('template_redirect', [__CLASS__, 'maybe_proxy'], 0);
        add_action('admin_menu', [__CLASS__, 'admin_menu']);
        add_action('admin_init', [__CLASS__, 'register_settings']);
        add_action('wp_head', [__CLASS__, 'print_discovery'], 2);
        register_activation_hook(__FILE__, [__CLASS__, 'activate']);
    }}

    public static function activate(): void {{
        if (!get_option(self::OPTION)) {{
            update_option(self::OPTION, CENTROPIC_EDGE_DEFAULT);
        }}
        self::add_rewrites();
        flush_rewrite_rules();
    }}

    public static function edge_base(): string {{
        $base = (string) get_option(self::OPTION, CENTROPIC_EDGE_DEFAULT);
        return untrailingslashit(esc_url_raw($base));
    }}

    public static function add_rewrites(): void {{
        add_rewrite_rule('^llms\\\\.txt$', 'index.php?centropic_edge=llms', 'top');
        add_rewrite_rule('^robots\\\\.txt$', 'index.php?centropic_edge=robots', 'top');
        add_rewrite_rule('^geopulse/signals\\\\.json$', 'index.php?centropic_edge=signals', 'top');
        add_rewrite_rule('^centropic/signals\\\\.json$', 'index.php?centropic_edge=signals', 'top');
        add_rewrite_rule('^\\\\.well-known/llms\\\\.txt$', 'index.php?centropic_edge=llms', 'top');
        add_rewrite_rule('^\\\\.well-known/organization\\\\.jsonld$', 'index.php?centropic_edge=jsonld', 'top');
    }}

    public static function query_vars(array $vars): array {{
        $vars[] = 'centropic_edge';
        return $vars;
    }}

    public static function maybe_proxy(): void {{
        $which = get_query_var('centropic_edge');
        if (!$which) {{
            // Fallback when another robots.txt plugin owns the route.
            $uri = isset($_SERVER['REQUEST_URI']) ? strtok($_SERVER['REQUEST_URI'], '?') : '';
            $map = [
                '/llms.txt' => 'llms',
                '/.well-known/llms.txt' => 'llms',
                '/robots.txt' => 'robots',
                '/geopulse/signals.json' => 'signals',
                '/centropic/signals.json' => 'signals',
                '/.well-known/organization.jsonld' => 'jsonld',
            ];
            $which = $map[$uri] ?? '';
        }}
        if (!$which) {{
            return;
        }}
        $paths = [
            'llms' => '/llms.txt',
            'robots' => '/robots.txt',
            'signals' => '/signals.json',
            'jsonld' => '/organization.jsonld',
        ];
        $suffix = $paths[$which] ?? '';
        if ($suffix === '') {{
            status_header(404);
            exit;
        }}
        $url = self::edge_base() . $suffix;
        $response = wp_remote_get($url, [
            'timeout' => 12,
            'headers' => [
                'Accept' => 'text/plain, application/json, */*',
                'User-Agent' => 'CentropicEdgeWordPress/' . CENTROPIC_EDGE_VERSION,
                'X-Centropic-Site' => home_url('/'),
            ],
        ]);
        if (is_wp_error($response)) {{
            status_header(502);
            header('Content-Type: text/plain; charset=utf-8');
            echo 'Centropic Edge upstream error';
            exit;
        }}
        $code = (int) wp_remote_retrieve_response_code($response);
        $body = (string) wp_remote_retrieve_body($response);
        $type = (string) wp_remote_retrieve_header($response, 'content-type');
        if ($type === '') {{
            $type = str_contains($suffix, 'json') ? 'application/json; charset=utf-8' : 'text/plain; charset=utf-8';
        }}
        status_header($code > 0 ? $code : 200);
        header('Content-Type: ' . $type);
        header('Cache-Control: public, max-age=300, stale-while-revalidate=3600');
        header('X-Centropic-Edge: wordpress');
        echo $body;
        exit;
    }}

    public static function print_discovery(): void {{
        $base = self::edge_base();
        if ($base === '') {{
            return;
        }}
        $llms = esc_url($base . '/llms.txt');
        $signals = esc_url($base . '/signals.json');
        echo "\\n<!-- Centropic Edge Signals -->\\n";
        echo '<link rel="alternate" type="text/plain" href="' . $llms . '" title="llms.txt" />' . "\\n";
        echo '<link rel="describedby" href="' . $signals . '" type="application/json" />' . "\\n";
    }}

    public static function admin_menu(): void {{
        add_options_page(
            'Centropic Edge',
            'Centropic Edge',
            'manage_options',
            'centropic-edge',
            [__CLASS__, 'render_settings']
        );
    }}

    public static function register_settings(): void {{
        register_setting('centropic_edge', self::OPTION, [
            'type' => 'string',
            'sanitize_callback' => 'esc_url_raw',
            'default' => CENTROPIC_EDGE_DEFAULT,
        ]);
    }}

    public static function render_settings(): void {{
        if (!current_user_can('manage_options')) {{
            return;
        }}
        $val = esc_url(self::edge_base());
        echo '<div class="wrap"><h1>Centropic Edge Signals</h1>';
        echo '<p>Incolla l\\'URL Edge dalla dashboard Centropic (es. https://centropic.ai/e/TOKEN).</p>';
        echo '<form method="post" action="options.php">';
        settings_fields('centropic_edge');
        echo '<table class="form-table"><tr><th scope="row"><label for="centropic_edge_base">Edge base URL</label></th>';
        echo '<td><input name="' . esc_attr(self::OPTION) . '" id="centropic_edge_base" type="url" class="regular-text" value="' . $val . '" required /></td></tr></table>';
        submit_button('Salva');
        echo '</form>';
        echo '<p>Site origin di riferimento: <code>' . esc_html('{site_origin}') . '</code></p>';
        echo '</div>';
    }}
}}

Centropic_Edge_Plugin::init();
"""


def _wordpress_readme() -> str:
    return """=== Centropic Edge Signals ===
Contributors: centropic
Tags: seo, ai, llms.txt, geo, aio
Requires at least: 6.0
Tested up to: 6.7
Stable tag: 1.0.0
License: GPLv2 or later

Proxies Centropic Edge Signals (llms.txt, robots.txt, signals.json) onto your WordPress domain.

== Installation ==
1. Upload the `centropic-edge` folder to `/wp-content/plugins/`
2. Activate the plugin
3. Settings → Centropic Edge → paste your `/e/<token>` URL
4. Visit https://yoursite.com/llms.txt
"""


def _shopify_liquid(*, edge_base: str) -> str:
    return f"""{{% comment %}}
  Centropic Edge Signals — drop into layout/theme.liquid inside <head>
  For /llms.txt and /robots.txt on the shop domain, use Cloudflare Worker
  or a Shopify app proxy pointing to {edge_base}
{{% endcomment %}}
<link rel="alternate" type="text/plain" href="{edge_base}/llms.txt" title="llms.txt" />
<link rel="describedby" href="{edge_base}/signals.json" type="application/json" />
"""


def _shopify_readme(*, edge_base: str) -> str:
    return f"""# Shopify + Centropic

1. Theme → Edit code → `layout/theme.liquid` → paste `snippets/centropic-edge.liquid` in `<head>`.
2. Root files (`/llms.txt`, `/robots.txt`) need an app proxy or Cloudflare Worker:

```
{edge_base}/llms.txt
{edge_base}/robots.txt
{edge_base}/signals.json
```

3. Optional: Cloudflare Worker from the `cloudflare/` folder in this ZIP.
"""


def _drupal_info() -> str:
    return """name: 'Centropic Edge Signals'
type: module
description: 'Proxies Centropic Edge AIO/GEO artifacts (llms.txt, robots, signals).'
core_version_requirement: '^10 || ^11'
package: SEO
"""


def _drupal_module() -> str:
    return """<?php

/**
 * @file
 * Centropic Edge Signals module.
 */

declare(strict_types=1);
"""


def _drupal_routing() -> str:
    return """centropic_edge.llms:
  path: '/llms.txt'
  defaults:
    _controller: '\\Drupal\\centropic_edge\\Controller\\EdgeProxyController::llms'
  requirements:
    _access: 'TRUE'
centropic_edge.robots:
  path: '/robots.txt'
  defaults:
    _controller: '\\Drupal\\centropic_edge\\Controller\\EdgeProxyController::robots'
  requirements:
    _access: 'TRUE'
centropic_edge.signals:
  path: '/geopulse/signals.json'
  defaults:
    _controller: '\\Drupal\\centropic_edge\\Controller\\EdgeProxyController::signals'
  requirements:
    _access: 'TRUE'
centropic_edge.jsonld:
  path: '/.well-known/organization.jsonld'
  defaults:
    _controller: '\\Drupal\\centropic_edge\\Controller\\EdgeProxyController::jsonld'
  requirements:
    _access: 'TRUE'
"""


def _drupal_controller(*, edge_base: str) -> str:
    return f"""<?php

declare(strict_types=1);

namespace Drupal\\centropic_edge\\Controller;

use Drupal\\Core\\Controller\\ControllerBase;
use Symfony\\Component\\HttpFoundation\\Response;

/**
 * Proxies Centropic Edge artifacts.
 */
final class EdgeProxyController extends ControllerBase {{

  private const DEFAULT_EDGE = '{edge_base}';

  private function proxy(string $suffix, string $contentType): Response {{
    $config = \\Drupal::config('centropic_edge.settings');
    $base = rtrim((string) ($config->get('edge_base') ?: self::DEFAULT_EDGE), '/');
    $url = $base . $suffix;
    try {{
      $client = \\Drupal::httpClient();
      $upstream = $client->get($url, [
        'timeout' => 12,
        'headers' => [
          'Accept' => 'text/plain, application/json, */*',
          'User-Agent' => 'CentropicEdgeDrupal/1.0',
        ],
      ]);
      $body = (string) $upstream->getBody();
      $status = $upstream->getStatusCode();
    }}
    catch (\\Throwable $e) {{
      return new Response('Centropic Edge upstream error', 502, [
        'Content-Type' => 'text/plain; charset=utf-8',
      ]);
    }}
    return new Response($body, $status, [
      'Content-Type' => $contentType,
      'Cache-Control' => 'public, max-age=300, stale-while-revalidate=3600',
      'X-Centropic-Edge' => 'drupal',
    ]);
  }}

  public function llms(): Response {{
    return $this->proxy('/llms.txt', 'text/plain; charset=utf-8');
  }}

  public function robots(): Response {{
    return $this->proxy('/robots.txt', 'text/plain; charset=utf-8');
  }}

  public function signals(): Response {{
    return $this->proxy('/signals.json', 'application/json; charset=utf-8');
  }}

  public function jsonld(): Response {{
    return $this->proxy('/organization.jsonld', 'application/ld+json; charset=utf-8');
  }}

}}
"""


def _drupal_readme(*, edge_base: str) -> str:
    return f"""# Drupal Centropic Edge

Default edge base: `{edge_base}`

```bash
drush en centropic_edge -y
drush cset centropic_edge.settings edge_base {edge_base}
drush cr
```
"""


def _generic_php_proxy(*, edge_base: str) -> str:
    return f"""<?php
/**
 * Centropic Edge universal PHP proxy (Joomla, PrestaShop, custom PHP, etc.)
 * Place in document root and route AIO paths here (see .htaccess / nginx samples).
 */
declare(strict_types=1);

$EDGE_BASE = getenv('CENTROPIC_EDGE_BASE') ?: '{edge_base}';
$EDGE_BASE = rtrim($EDGE_BASE, '/');

$map = [
    '/llms.txt' => '/llms.txt',
    '/.well-known/llms.txt' => '/llms.txt',
    '/robots.txt' => '/robots.txt',
    '/geopulse/signals.json' => '/signals.json',
    '/centropic/signals.json' => '/signals.json',
    '/.well-known/organization.jsonld' => '/organization.jsonld',
];

$uri = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
$suffix = $map[$uri] ?? null;
if ($suffix === null) {{
    // Allow ?path=llms|robots|signals|jsonld when used as front controller.
    $q = $_GET['path'] ?? '';
    $alias = [
        'llms' => '/llms.txt',
        'robots' => '/robots.txt',
        'signals' => '/signals.json',
        'jsonld' => '/organization.jsonld',
    ];
    $suffix = $alias[$q] ?? null;
}}
if ($suffix === null) {{
    http_response_code(404);
    header('Content-Type: text/plain; charset=utf-8');
    echo "Not found";
    exit;
}}

$url = $EDGE_BASE . $suffix;
$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_TIMEOUT => 12,
    CURLOPT_HTTPHEADER => [
        'Accept: text/plain, application/json, */*',
        'User-Agent: CentropicEdgePHP/1.0',
    ],
]);
$body = curl_exec($ch);
$status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
$ctype = curl_getinfo($ch, CURLINFO_CONTENT_TYPE) ?: (
    str_contains($suffix, 'json') ? 'application/json; charset=utf-8' : 'text/plain; charset=utf-8'
);
$err = curl_error($ch);
curl_close($ch);

if ($body === false) {{
    http_response_code(502);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Upstream error: ' . $err;
    exit;
}}

http_response_code($status > 0 ? $status : 200);
header('Content-Type: ' . $ctype);
header('Cache-Control: public, max-age=300, stale-while-revalidate=3600');
header('X-Centropic-Edge: php');
echo $body;
"""


def _apache_htaccess() -> str:
    return """# Centropic Edge — Apache rewrite to centropic-proxy.php
<IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteRule ^llms\\.txt$ centropic-proxy.php?path=llms [L]
  RewriteRule ^robots\\.txt$ centropic-proxy.php?path=robots [L]
  RewriteRule ^geopulse/signals\\.json$ centropic-proxy.php?path=signals [L]
  RewriteRule ^centropic/signals\\.json$ centropic-proxy.php?path=signals [L]
  RewriteRule ^\\.well-known/llms\\.txt$ centropic-proxy.php?path=llms [L]
  RewriteRule ^\\.well-known/organization\\.jsonld$ centropic-proxy.php?path=jsonld [L]
</IfModule>
"""


def _nginx_conf(*, edge_base: str) -> str:
    base = edge_base.rstrip("/")
    return f"""# Centropic Edge — Nginx proxy (preferred) or front-controller to PHP
location = /llms.txt {{
  proxy_pass {base}/llms.txt;
  proxy_set_header Accept "text/plain, */*";
  add_header Cache-Control "public, max-age=300, stale-while-revalidate=3600";
  add_header X-Centropic-Edge nginx;
}}
location = /robots.txt {{
  proxy_pass {base}/robots.txt;
  proxy_set_header Accept "text/plain, */*";
  add_header Cache-Control "public, max-age=300, stale-while-revalidate=3600";
  add_header X-Centropic-Edge nginx;
}}
location = /geopulse/signals.json {{
  proxy_pass {base}/signals.json;
  add_header Cache-Control "public, max-age=300, stale-while-revalidate=3600";
  add_header X-Centropic-Edge nginx;
}}
location = /.well-known/organization.jsonld {{
  proxy_pass {base}/organization.jsonld;
  add_header Cache-Control "public, max-age=300, stale-while-revalidate=3600";
  add_header X-Centropic-Edge nginx;
}}
"""


def _generic_php_readme(*, edge_base: str) -> str:
    return f"""# Generic PHP / Apache / Nginx

Edge base: `{edge_base}`

1. Copy `centropic-proxy.php` to the web root (or set `CENTROPIC_EDGE_BASE` env).
2. Apache: merge `.htaccess.centropic` into your `.htaccess`.
3. Nginx: include `nginx-centropic.conf` (direct proxy, no PHP needed).
"""


def _netlify_toml(*, edge_base: str) -> str:
    base = edge_base.rstrip("/")
    return f"""[[redirects]]
  from = "/llms.txt"
  to = "{base}/llms.txt"
  status = 200
  force = true

[[redirects]]
  from = "/robots.txt"
  to = "{base}/robots.txt"
  status = 200
  force = true

[[redirects]]
  from = "/geopulse/signals.json"
  to = "{base}/signals.json"
  status = 200
  force = true

[[redirects]]
  from = "/.well-known/organization.jsonld"
  to = "{base}/organization.jsonld"
  status = 200
  force = true
"""


def _netlify_redirects(*, edge_base: str) -> str:
    base = edge_base.rstrip("/")
    return f"""/llms.txt  {base}/llms.txt  200!
/robots.txt  {base}/robots.txt  200!
/geopulse/signals.json  {base}/signals.json  200!
/.well-known/organization.jsonld  {base}/organization.jsonld  200!
"""
