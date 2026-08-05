# Centropic brand — Formal Futurist

Production visual system for `centropic.ai`.

## Direction
Void Graphite surfaces, Instrument Teal accent, Platinum type. Instrumental and quiet — not neon cyberpunk, not holographic violet.

## Assets
- `static/img/logo.svg` — orbital instrument mark (teal / steel)
- `static/img/logo.png` — raster mark (favicon / apple-touch)
- `static/img/logo-mark.svg` — compact mark
- `static/img/hero-citation-field.svg` — marketing hero visual
- `static/img/og-share.png` — Open Graph / social share (1200×630)
- Jinja lockup: `templates/partials/holo_brand.html` (name retained; styling is formal)

## Palette
| Token | Hex | Role |
|---|---|---|
| Void Graphite | `#04060A` | Page background |
| Instrument card | `#0A0E14` | Elevated surface |
| Border steel | `#1A222D` | Hairlines |
| Instrument Teal | `#6EC6C0` | Primary accent |
| Steel Blue | `#4A7C8C` | Secondary accent |
| Platinum | `#F5F7FA` | Primary text |
| Muted steel | `#8B97A8` | Secondary text |

`--brand-violet` aliases to teal for legacy class names — do not reintroduce purple.

## Typography
| Role | Family |
|---|---|
| Display | Space Grotesk |
| Body | IBM Plex Sans |
| Mono | IBM Plex Mono |

Do not use Inter, Roboto, Sora, or Plus Jakarta Sans.

## Hierarchy rules
1. Brand (`centropic.ai`) is a hero-level signal on marketing first viewports — never overpowered by the headline.
2. Hero budget: brand + one headline + one supporting sentence + one CTA group + one dominant visual.
3. No floating badges/chips on hero media.
4. Cards only when they contain a user interaction (plans, forms). Prefer open sections elsewhere.
5. Prefer single soft depth shadows over cyan glow stacks; avoid `rounded-full` pills for status chrome.

## Motion
Landing keeps intentional motion: aurora drift, signal sweep, citation field rise, copy/headline rise. Always respect `prefers-reduced-motion`.
