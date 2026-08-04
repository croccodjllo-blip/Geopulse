# Centropic GEO UI (React)

Enterprise GEO charts kit (React 19 + Tailwind + Recharts).

## Scripts

```bash
npm install
npm run dev          # Vite on :5173 (demo defaults when no Flask payload)
npm run build        # → static/geo-ui/ (served by Flask)
npm run typecheck
```

## Production embed

Authenticated route: `/dashboard/geo-ui` → `templates/geo_ui.html`

- Sets `window.__CENTROPIC_GEO_EMBED__ = true` (hides React sidebar)
- Injects `window.__CENTROPIC_GEO_DATA__` from `services/geo_ui_payload.py`
  (latest analysis: SoM, engines, findings, SoV trend — **no demo KPIs**)
- Serves hashed assets from `static/geo-ui/assets/` via `resolve_geo_ui_assets()`

Standalone Vite (`npm run dev`) still uses demo defaults for design work.
