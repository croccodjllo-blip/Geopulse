# Centropic brand — Logo Chrome

Production visual system for `centropic.ai`.

## Direction
Void-black surfaces, chrome/silver accent (`#C9D3DD` / `#5B6B7A`) sampled directly from the logo emblem — **no purple/violet accent anywhere** (retired 2026-08-05, on explicit user request, superseding the short-lived Nova Violet direction). Inter type. Card-heavy dashboard energy — icon-badged metrics, a per-engine radar chart — carried over from Nova Violet; only the color changed. Nebula bloom (blue + violet) stays behind the landing hero backdrop only and is purely atmospheric, never an interactive-UI color.

Semantic state colors are deliberately **not** the brand accent: success stays green (`--ok: #22C55E`), warning amber, danger red.

### Per-plan accent (dashboard only)
Each dashboard plan tier gets its own uniform accent, used consistently for both the background atmosphere *and* every "image" component (stat-tile badge, SoV ring, radar chart, credits bar) — driven by `--plan-accent` / `--plan-accent-deep`, set per `body.dash-plan--*` class in `static/css/app.css`:

| Plan | Accent | Hex |
|---|---|---|
| Free | Cool steel silver | `#8BA3BD` |
| Plus | Platinum teal | `#3FA8B5` |
| Business | Copper / bronze | `#D4A574` |

Marketing pages and admin (no `dash-plan--*` class) fall back to the global chrome accent (`--plan-accent: var(--brand-cyan)`). When adding a new "image"/graphic dashboard component, use `var(--plan-accent)`/`var(--plan-accent-deep)`, not a hardcoded hex — that is what makes it plan-uniform automatically.

## Assets
- `static/img/logo-cosmic-emblem.png` — source 3D chrome star-shield emblem, monogram **C**, orbital ring + satellite nodes (1024²). Edit this to change the mark, then re-render everything below from it.
- `static/img/logo.png` — primary mark, every header/hero/page-intro/auth `<img>` points here directly (512²)
- `static/img/logo-mark.png` — compact mark for the sidebar (128²)
- `static/img/apple-touch-icon.png` (180²), `favicon-32.png`, `favicon-16.png` — small icon renders cropped tight for legibility
- `static/img/hero-cosmic.jpg` — nebula backdrop used behind the landing hero
- `static/img/og-share.jpg` — Open Graph / social share (1200×630), cropped from the hero art
- Jinja lockup: `templates/partials/holo_brand.html` (legacy name, still current)

**Do not** wrap the mark in an SVG `<image href="...png">` again to avoid touching templates — it was tried and reverted (2026-08-05): browsers render an SVG loaded via `<img src="logo.svg">` in a restricted "image context", and the internal `<image>` reference to the external PNG did not reliably paint in production, making the logo (and every place reusing the same trick: favicon, sidebar mark, auth pages) go blank. Every logo `<img>` must point at a real raster file directly.

## Mark concept
Faceted chrome star-shield · bold metallic **C** monogram · upward arrow silhouette · thin orbital ring with glowing satellite nodes. Photoreal 3D chrome render, not a flat vector icon — this is intentional; do not flatten it back into a line-art SVG.

## Wordmark
`CENTROPIC.AI` — **uppercase**, metallic chrome gradient text (`background-clip: text`), on the hero and page-intro brand rows. This replaced the previous lowercase `centropic.ai` treatment. Nav/sidebar chrome may keep the smaller lowercase word next to the compact mark where space is tight (`templates/partials/holo_brand.html`, `.brand-mark__word`).

## Palette
| Token | Hex | Role |
|---|---|---|
| Void | `#04060A` | Page background |
| Card | `#0A0E14` | Elevated surface |
| Border | `#1A222D` | Hairlines |
| Chrome silver | `#C9D3DD` | Primary accent (default; overridden per plan on dashboard pages) |
| Steel shadow | `#5B6B7A` | Secondary accent / gradient stop |
| Nebula blue | `#2E4A78` | Landing hero atmosphere only |
| Nebula violet | `#4A3468` | Landing hero atmosphere only — atmosphere-only, not a UI color |
| Platinum | `#E8EEF4` | Primary text |
| Muted | `#8B97A8` | Secondary text |
| Success | `#22C55E` | Positive delta / ok state (not the brand accent) |
| Warning | `#F59E0B` | Warn state |
| Danger | `#EF4444` | Critical / negative delta |

`--brand-violet` aliases to the primary chrome accent for legacy class names — it is a naming leftover, not an instruction to use violet. Nebula blue/violet are atmosphere-only tokens (landing hero background glow) — never used for interactive UI or for any of the per-plan dashboard accents above.

## Typography
| Role | Family |
|---|---|
| Display / body | Inter |
| Mono (data-dense chrome: code, IDs, tabular labels) | IBM Plex Mono |

Do not use Roboto, Sora, or Plus Jakarta Sans.

## Dashboard components
- **Stat tiles** (`templates/partials/ui_metric.html`): circular gradient icon badge (`--plan-accent-deep` → `--plan-accent`) + big Inter number + uppercase label/hint. Pass `icon='aio'|'geo'|'findings'` when including. No fabricated deltas/sparklines — Centropic never shows a trend it hasn't actually measured.
- **Engine radar** (`services/engine_breakdown.py::_radar_geometry`, rendered in `templates/dashboard.html` inside the SoV panel): server-computed N-axis polygon from real per-engine `propensity` — no client-side JS trig needed. Colored via `var(--plan-accent)`. Reuse this helper if another panel needs a radar/spider view over per-engine data.
- **Sparkle decoration**: `.sov-panel::before/::after` — two small white dots, used sparingly on the SoV "overview" card only. Do not spam sparkle on every card.
- **Pulse Core AIO gauge** (`--pc-grad-a`/`--pc-glow`) is colored by *score quality band* (peak/high/mid/low/crit), not by plan — leave that logic alone; it is answering a different question ("is this score good?") than the plan accent ("whose dashboard is this?").

## Hierarchy rules
1. Brand (`CENTROPIC.AI`) is a hero-level signal on marketing first viewports — never overpowered by the headline.
2. Hero budget: brand + one headline + one supporting sentence + one CTA group + one dominant visual (now the nebula + chrome emblem).
3. No floating badges/chips on hero media.
4. Cards only when they contain a user interaction (plans, forms). Prefer open sections elsewhere.
5. Prefer single soft depth shadows over glow stacks; avoid `rounded-full` pills for status chrome.

## Motion
Landing keeps intentional motion: aurora drift, signal sweep, citation field rise, copy/headline rise. Always respect `prefers-reduced-motion`.
