# Centropic GEO UI (React)

Enterprise dashboard kit: Vite + React 19 + Tailwind + Recharts.

## Develop

```bash
npm install
npm run dev          # http://localhost:5173
npm run typecheck
npm run build        # → static/geo-ui/ (served by Flask)
```

## Flask

Authenticated SPA: `/dashboard/geo-ui` → `static/geo-ui/index.html`.

Components live in `components/`; app shell in `src/`. Brand tokens are in `tailwind.config.ts` (Deep Space Navy / Quantum Cyan / Electric Violet).
