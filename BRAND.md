# Centropic brand — Logo Chrome

Production visual system for `centropic.ai`.

## Direction
Void-black surfaces, chrome/silver accent (`#C9D3DD` / `#5B6B7A`) sampled directly from the logo emblem — **no purple/violet accent anywhere** (retired 2026-08-05, on explicit user request, superseding the short-lived Nova Violet direction). Inter type. Card-heavy dashboard energy — icon-badged metrics, a per-engine radar chart — carried over from Nova Violet; only the color changed. Nebula bloom (blue + violet) stays behind the landing hero backdrop only and is purely atmospheric, never an interactive-UI color.

Semantic state colors are deliberately **not** the brand accent: success stays green (`--ok: #22C55E`), warning amber, danger red.

### Per-plan canvas + accent (logged-in shell)
When a user is logged in, `body.dash-plan--free|plus|business` remaps the **entire surface canvas** (`--brand-bg`, `--brand-card`, `--brand-elevated`, `--brand-border`, `--bg-gradient`) to one hue family per plan — body, sidebar, header, workspace strip, footer, and panels all read the same tokens. Accents (`--plan-accent` / `--plan-accent-deep`) color interactive/image chrome only (stat-tile badge, SoV ring, radar, credits bar, active nav). Do **not** paint sidebar/header/strip with a second solid gradient hue.

| Plan | Accent | Canvas base (`--brand-bg`) |
|---|---|---|
| Free | Steel `#8BA3BD` | `#0A1018` |
| Plus | Platinum teal `#3FA8B5` | `#061210` |
| Business | Copper `#D4A574` | `#100C08` |

Marketing/admin with no plan class keep the global chrome void (`--brand-bg: #04060A`, `--plan-accent: var(--brand-cyan)`). New surfaces must use `var(--brand-*)` / `var(--plan-accent*)`, never a hardcoded navy/teal/copper hex.

## Assets
- `static/img/logo.svg` — **primary mark, true self-contained vector** (paths/gradients only, no external `<image>` refs). Every header/hero/page-intro/auth `<img>` points here directly (viewBox 128×128).
- `static/img/logo-mark.svg` — compact vector mark for the sidebar (viewBox 64×64, simplified geometry for ≤28px legibility).
- `static/favicon.svg` — same compact-mark design.
- `static/img/logo.png` / `logo-mark.png` / `apple-touch-icon.png` / `favicon-32.png` / `favicon-16.png` — raster renders of the SVGs above (`cairosvg`), used only where raster is required: `<link rel="apple-touch-icon">`, JSON-LD `logo`/`image`, `<link rel="icon" sizes="any">` fallback.
- `static/img/hero-signal-field.jpg` — landing hero full-bleed atmosphere (ultrawide ~21:9, `object-fit: cover` via `.hero-visual__photo`). Abstract chrome signal-field; **no logo/monogram/wordmark** — mark stays in the HTML lockup.
- `static/img/og-share.jpg` — Open Graph / social share (1200×630), cropped from the hero art.
- Jinja lockup: `templates/partials/holo_brand.html` (legacy name, still current).

**Two banned patterns, both tried and reverted on the same mark:**
1. *Photoreal 3D raster as "the logo"* (2026-08-05, "Cosmic Chrome"/"Nova Violet" sessions) — looked good large but couldn't stay crisp at favicon/sidebar sizes and required a separate raster pipeline.
2. *SVG wrapping that raster via `<image href="...png">`* to avoid touching templates — browsers render an SVG loaded via `<img src="logo.svg">` in a restricted "image context", and the internal `<image>` reference to the external PNG did not reliably paint in production, so the logo went blank everywhere.

The current mark avoids both: `logo.svg`/`logo-mark.svg`/`favicon.svg` are genuine vector shapes (polygon/ellipse/path + linear/radial gradients, all inline, zero external refs) — safe to use directly via `<img src="...svg">` in every browser, and infinitely scalable (verified 16px favicon up to 220px auth-page render).

## Mark concept
Faceted chrome hex chassis · dashed orbital ellipse ring with a glowing satellite node · bold chrome-gradient **C** monogram formed from an open ring stroke. Flat/gradient vector, not a photoreal 3D render — this is intentional; do not swap it back to a raster photo.

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

## Proprietary metric (category)
- **CVI — Centropic Visibility Index**: flagship product metric (composite 0–100 + letter **DDD→AAA** from AIO+GEO with finding penalties). User-facing name for the former “Indice”. Do not conflate with Moz DA / Ahrefs DR.
- **AIO / GEO**: keep as named *components* of CVI (not replacements for CVI).
- **Citation share**: user-facing framing for generative mention samples (stochastic). Legacy UI may still say SoV; methodology copy should prefer “citation share” over advertising “Share of Voice”.

## Dashboard components
- **Stat tiles** (`templates/partials/ui_metric.html`): circular gradient icon badge (`--plan-accent-deep` → `--plan-accent`) + big Inter number + uppercase label/hint. Pass `icon='aio'|'geo'|'findings'` when including. No fabricated deltas/sparklines — Centropic never shows a trend it hasn't actually measured.
- **Engine radar** (`services/engine_breakdown.py::_radar_geometry`, rendered in `templates/dashboard.html` inside the SoV panel): server-computed N-axis polygon from real per-engine `propensity` — no client-side JS trig needed. Colored via `var(--plan-accent)`. Reuse this helper if another panel needs a radar/spider view over per-engine data.
- **Sparkle decoration**: `.sov-panel::before/::after` — two small white dots, used sparingly on the SoV "overview" card only. Do not spam sparkle on every card.
- **Pulse Core AIO gauge** (`--pc-grad-a`/`--pc-glow`) is colored by *score quality band* (peak/high/mid/low/crit), not by plan — leave that logic alone; it is answering a different question ("is this score good?") than the plan accent ("whose dashboard is this?").

## Hierarchy rules
1. Brand (`CENTROPIC.AI`) is a hero-level signal on marketing first viewports — never overpowered by the headline.
2. Hero budget: brand + one headline + one supporting sentence + one CTA group + one dominant visual (signal-field atmosphere + citation map overlay — mark only in the HTML lockup).
3. No floating badges/chips on hero media.
4. Cards only when they contain a user interaction (plans, forms). Prefer open sections elsewhere.
5. Prefer single soft depth shadows over glow stacks; avoid `rounded-full` pills for status chrome.

## Motion
Landing keeps intentional motion: aurora drift, signal sweep, citation field rise, copy/headline rise. Always respect `prefers-reduced-motion`.
