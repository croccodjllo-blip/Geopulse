# Centropic holographic brand module

Production UI for the hyper-futuristic `centropic.ai` lockup.

## Assets
- `static/img/logo.svg` — vortex + ascending vector emblem (neon cyan / quantum blue / UV violet)
- `static/favicon.svg` — compact mark
- `components/HoloEmblem.tsx` — animated SVG + orbital particle canvas
- `components/BrandLockup.tsx` — iridescent wordmark
- `components/BrandModule.tsx` — hero / panel / inline layouts

## Palette
| Token | Hex |
|---|---|
| Neon Electric Cyan | `#00F0FF` |
| Quantum Blue | `#0066FF` |
| Holographic Violet | `#8A2BE2` |
| Liquid Chrome | `#080B10` → `#121824` |

## Usage
```tsx
import { BrandModule, HoloEmblem, BrandLockup } from "@/components";

<BrandModule variant="hero" ctaHref="/register" />
<BrandModule variant="panel" />
<BrandLockup size="md" showTagline particles />
```

Jinja: `templates/partials/holo_brand.html`

No R3F dependency — canvas particles keep the Flask deploy light.
