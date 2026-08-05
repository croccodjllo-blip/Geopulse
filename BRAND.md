# Centropic brand — Cosmic Chrome

Production visual system for `centropic.ai`.

## Direction
Deep space void, polished chrome-silver emblem, restrained nebula bloom (blue + violet) behind the hero only. Cinematic instrument, not neon cyberpunk, not flat corporate teal.

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
| Void | `#04060A` | Page background |
| Instrument card | `#0A0E14` | Elevated surface |
| Border steel | `#1A222D` | Hairlines |
| Chrome silver | `#C9D3DD` | Primary accent (was Instrument Teal `#6EC6C0`) |
| Steel chrome | `#5B6B7A` | Secondary accent (was Steel Blue `#4A7C8C`) |
| Nebula blue | `#2E4A78` | Hero atmosphere only |
| Nebula violet | `#4A3468` | Hero atmosphere only |
| Platinum | `#F5F7FA` | Primary text |
| Muted steel | `#8B97A8` | Secondary text |

`--brand-violet` aliases to chrome silver for legacy class names. Nebula blue/violet are atmosphere-only tokens (hero background glow) — never used for interactive UI (buttons, links, focus rings), which stay chrome silver for contrast and consistency.

## Typography
| Role | Family |
|---|---|
| Display | Space Grotesk |
| Body | IBM Plex Sans |
| Mono | IBM Plex Mono |

Do not use Inter, Roboto, Sora, or Plus Jakarta Sans.

## Hierarchy rules
1. Brand (`CENTROPIC.AI`) is a hero-level signal on marketing first viewports — never overpowered by the headline.
2. Hero budget: brand + one headline + one supporting sentence + one CTA group + one dominant visual (now the nebula + chrome emblem).
3. No floating badges/chips on hero media.
4. Cards only when they contain a user interaction (plans, forms). Prefer open sections elsewhere.
5. Prefer single soft depth shadows over glow stacks; avoid `rounded-full` pills for status chrome.

## Motion
Landing keeps intentional motion: aurora drift, signal sweep, citation field rise, copy/headline rise. Always respect `prefers-reduced-motion`.
