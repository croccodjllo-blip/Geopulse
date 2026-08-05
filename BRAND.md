# Centropic brand — Nova Violet

Production visual system for `centropic.ai`.

## Direction
Near-black surfaces, vivid violet/magenta accent (`#B84FF0` / `#7C3AED`), Inter type. Modern SaaS dashboard energy — card-heavy, icon-badged metrics, a per-engine radar chart — instead of the previous flat instrument-panel look. Nebula bloom (blue + violet) stays behind the hero backdrop only; the emblem itself is unchanged (chrome star-shield, monogram **C**).

Semantic state colors are deliberately **not** the brand accent: success stays green (`--ok: #22C55E`), warning amber, danger red — so delta pills and status badges stay legible against the violet UI, matching how real dashboard templates (e.g. Landzy-style admin panels) separate "brand color" from "status color".

## Assets
- `static/img/logo-cosmic-emblem.png` — source 3D chrome star-shield emblem, monogram **C**, orbital ring + satellite nodes (1024²)
- `static/img/logo.svg` / `static/img/logo-mark.svg` / `static/favicon.svg` — thin SVG wrappers around the emblem PNG (`<image>` ref), so every existing `url_for('static', filename='img/logo.svg')` call across templates renders the new mark with no template changes
- `static/img/logo.png` — raster fallback 512² (apple-touch / JSON-LD)
- `static/img/apple-touch-icon.png`, `favicon-32.png`, `favicon-16.png` — small icon renders cropped tight for legibility
- `static/img/hero-cosmic.jpg` — nebula backdrop used behind the landing hero
- `static/img/og-share.jpg` — Open Graph / social share (1200×630), cropped from the hero art
- Jinja lockup: `templates/partials/holo_brand.html` (legacy name, still current)

## Mark concept
Faceted chrome star-shield · bold metallic **C** monogram · upward arrow silhouette · thin orbital ring with glowing satellite nodes. Photoreal 3D chrome render, not a flat vector icon — this is intentional; do not flatten it back into a line-art SVG.

## Wordmark
`CENTROPIC.AI` — **uppercase**, metallic chrome gradient text (`background-clip: text`), on the hero and page-intro brand rows. This replaced the previous lowercase `centropic.ai` treatment. Nav/sidebar chrome may keep the smaller lowercase word next to the compact mark where space is tight (`templates/partials/holo_brand.html`, `.brand-mark__word`).

## Palette
| Token | Hex | Role |
|---|---|---|
| Void | `#0A0710` | Page background |
| Card | `#130F1F` | Elevated surface |
| Border | `#241D36` | Hairlines |
| Violet | `#B84FF0` | Primary accent (buttons, links, active nav, radar/ring charts) |
| Deep violet | `#7C3AED` | Secondary accent / gradient stop |
| Nebula blue | `#2E4A78` | Hero atmosphere only |
| Nebula violet | `#4A3468` | Hero atmosphere only |
| Platinum | `#F2EEF8` | Primary text |
| Muted | `#8B8599` | Secondary text |
| Success | `#22C55E` | Positive delta / ok state (not the brand accent) |
| Warning | `#F59E0B` | Warn state |
| Danger | `#EF4444` | Critical / negative delta |

`--brand-violet` aliases to the primary accent for legacy class names. Nebula blue/violet are atmosphere-only tokens (hero background glow) — never used for interactive UI.

## Typography
| Role | Family |
|---|---|
| Display / body | Inter |
| Mono (data-dense chrome: code, IDs, tabular labels) | IBM Plex Mono |

Do not use Roboto, Sora, or Plus Jakarta Sans. (Inter replaced Space Grotesk + IBM Plex Sans for the Nova Violet direction.)

## Dashboard components (Nova Violet)
- **Stat tiles** (`templates/partials/ui_metric.html`): circular gradient icon badge (`--brand-blue` → `--brand-cyan`) + big Inter number + uppercase label/hint. Pass `icon='aio'|'geo'|'findings'` when including. No fabricated deltas/sparklines — Centropic never shows a trend it hasn't actually measured.
- **Engine radar** (`services/engine_breakdown.py::_radar_geometry`, rendered in `templates/dashboard.html` inside the SoV panel): server-computed N-axis polygon from real per-engine `propensity` — no client-side JS trig needed. Reuse this helper if another panel needs a radar/spider view over per-engine data.
- **Sparkle decoration**: `.sov-panel::before/::after` — two small white dots, used sparingly on the SoV "overview" card only. Do not spam sparkle on every card.

## Hierarchy rules
1. Brand (`CENTROPIC.AI`) is a hero-level signal on marketing first viewports — never overpowered by the headline.
2. Hero budget: brand + one headline + one supporting sentence + one CTA group + one dominant visual (now the nebula + chrome emblem).
3. No floating badges/chips on hero media.
4. Cards only when they contain a user interaction (plans, forms). Prefer open sections elsewhere.
5. Prefer single soft depth shadows over glow stacks; avoid `rounded-full` pills for status chrome.

## Motion
Landing keeps intentional motion: aurora drift, signal sweep, citation field rise, copy/headline rise. Always respect `prefers-reduced-motion`.
