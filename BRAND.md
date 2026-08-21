# Centropic brand — Logo Chrome

Production visual system for `centropic.ai`.

## Direction
Charcoal surfaces (`#121212`), warm gold/amber accent (`#E8A04A` / `#C47A2C`) sampled from the C-arc emblem — **no purple/violet and no teal** as UI accents. Inter type. Card-heavy dashboard energy. Warm nebula/orbital bloom stays atmospheric (hero/dash haze), never a second interactive color.

Semantic state colors are deliberately **not** the brand accent: success stays green (`--ok: #22C55E`), warning amber, danger red.

### Per-plan canvas + accent (logged-in shell)
When a user is logged in, `body.dash-plan--free|plus|business` remaps the **entire surface canvas** (`--brand-bg`, `--brand-card`, `--brand-elevated`, `--brand-border`, `--bg-gradient`) to one hue family per plan — body, sidebar, header, workspace strip, footer, and panels all read the same tokens. Accents (`--plan-accent` / `--plan-accent-deep`) color interactive/image chrome only (stat-tile badge, SoV ring, radar, credits bar, active nav). Do **not** paint sidebar/header/strip with a second solid gradient hue.

| Plan | Accent | Canvas base (`--brand-bg`) |
|---|---|---|
| Free | Champagne `#C4A574` | `#121212` |
| Plus | Amber gold `#E8A04A` | `#121212` |
| Business | Copper `#D4A574` | `#14110C` |

Marketing/admin with no plan class keep the global charcoal void (`--brand-bg: #121212`, `--plan-accent: var(--brand-cyan)`). New surfaces must use `var(--brand-*)` / `var(--plan-accent*)`, never a hardcoded navy/teal/chrome hex.

## Assets
- `static/img/logo.svg` — **primary mark, true self-contained vector** (paths/gradients only, no external `<image>` refs, **no charcoal plate**). The C sits on whatever surface loads it (hero nebula, charcoal chrome). Every header/hero/page-intro/auth `<img>` points here directly (viewBox 128×128).
- `static/img/logo-mark.svg` — compact vector mark for the sidebar (viewBox 64×64, simplified geometry for ≤28px legibility, same transparent canvas).
- `static/favicon.svg` — same mark **with** a `#121212` plate so the tab icon stays readable on light browser chrome.
- `static/img/logo.png` / `logo-mark.png` / `apple-touch-icon.png` / `favicon-32.png` / `favicon-16.png` — raster renders of the SVGs above (`cairosvg`), used only where raster is required: `<link rel="apple-touch-icon">`, JSON-LD `logo`/`image`, `<link rel="icon" sizes="any">` fallback.
- `static/img/bg-void-chrome.jpg` / `bg-void-chrome-mobile.jpg` — site-wide void charcoal canvas with teal particle glow (preview 1–3 atmosphere). Used as marketing hero photo and dash body backdrop.
- `static/img/hero-signal-field.jpg` — legacy hero art (superseded on landing by `bg-void-chrome.jpg`).
- `static/img/og-share.jpg` — Open Graph / social share (1200×630), cropped from the hero art.
- Jinja lockup: `templates/partials/holo_brand.html` (legacy name, still current).

**Two banned patterns, both tried and reverted on the same mark:**
1. *Photoreal 3D raster as "the logo"* (2026-08-05, "Cosmic Chrome"/"Nova Violet" sessions) — looked good large but couldn't stay crisp at favicon/sidebar sizes and required a separate raster pipeline.
2. *SVG wrapping that raster via `<image href="...png">`* to avoid touching templates — browsers render an SVG loaded via `<img src="logo.svg">` in a restricted "image context", and the internal `<image>` reference to the external PNG did not reliably paint in production, so the logo went blank everywhere.

The current mark avoids both: `logo.svg`/`logo-mark.svg`/`favicon.svg` are genuine vector shapes (polygon/ellipse/path + linear/radial gradients, all inline, zero external refs) — safe to use directly via `<img src="...svg">` in every browser, and infinitely scalable (verified 16px favicon up to 220px auth-page render).

## Mark concept
Chrome void disc · dashed orbital ellipse with satellite node · bold chrome-gradient **C** monogram (open ring stroke). Flat/gradient vector, not a photoreal 3D render — intentional; do not swap to a raster photo. (Hex chassis retired 2026-08-19 in favor of the circular preview lockup.)

## Wordmark
`CENTROPIC.AI` — **uppercase**, metallic chrome gradient text (`background-clip: text`), **only on the landing `#hero-brand` lockup**. Page-intro / auth brand rows keep the plain lowercase `centropic.ai` wordmark so they never compete with that page’s H1. Nav/sidebar chrome may keep the smaller lowercase word next to the compact mark where space is tight (`templates/partials/holo_brand.html`, `.brand-mark__word`).

## Palette
| Token | Hex | Role |
|---|---|---|
| Void | `#121212` | Page background |
| Card | `#1A1612` | Elevated surface |
| Border | `#3A2E22` | Hairlines |
| Warm gold | `#E8A04A` | Primary accent (default; overridden per plan on dashboard pages) |
| Deep amber | `#C47A2C` | Secondary accent / gradient stop |
| Nebula amber | `#8A4E16` | Landing hero atmosphere only |
| Nebula ember | `#5C3010` | Landing hero atmosphere only — atmosphere-only, not a UI color |
| Warm ivory | `#F3EDE3` | Primary text |
| Muted | `#B8A894` | Secondary text |
| Success | `#22C55E` | Positive delta / ok state (not the brand accent) |
| Warning | `#F59E0B` | Warn state |
| Danger | `#EF4444` | Critical / negative delta |

`--brand-violet` / Tailwind `brand.violet` remain as **legacy aliases** of chrome/steel — never paint purple. Prefer `--brand-chrome` / `--brand-steel` and tone `"steel"` in new code. Nebula blue/violet tokens power the landing hero aurora only (`var(--nebula-*)` in `.hero-visual__aurora`) — never interactive UI or plan accents.

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
