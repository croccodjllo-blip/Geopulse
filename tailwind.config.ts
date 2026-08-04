import type { Config } from "tailwindcss";

/**
 * Centropic.ai — Enterprise GEO/AIO design tokens.
 * Flask templates consume the compiled/hand-authored CSS in static/css/app.css;
 * this config is the source of truth for Tailwind utility generation and future UI kits.
 */
const config: Config = {
  darkMode: ["class"],
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.{js,ts}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: "#0B0F19", // Deep Space Navy
          card: "#111827", // Dark Slate
          border: "#1F2937", // Border subtle
          cyan: "#00F0FF", // Quantum Cyan
          violet: "#7000FF", // Electric Violet
          muted: "#94A3B8", // Slate Grey
        },
        // Legacy Centropic aliases → new enterprise palette
        centropic: {
          chaos: "#0B0F19",
          core: "#00F0FF",
          flow: "#00F0FF",
          violet: "#7000FF",
          clarity: "#F8FAFC",
          card: "#111827",
          border: "#1F2937",
          muted: "#94A3B8",
        },
        chaos: "#0B0F19",
        core: "#00F0FF",
        flow: "#00F0FF",
        clarity: "#F8FAFC",
      },
      boxShadow: {
        glow: "0 0 15px rgba(0, 240, 255, 0.15)",
        "glow-violet": "0 0 15px rgba(112, 0, 255, 0.2)",
      },
      backgroundImage: {
        "centropic-bg":
          "radial-gradient(1200px 600px at 10% -10%, rgba(112, 0, 255, 0.18), transparent 55%), radial-gradient(900px 500px at 90% 0%, rgba(0, 240, 255, 0.12), transparent 50%), linear-gradient(160deg, #0B0F19 0%, #0F172A 55%, #0B0F19 100%)",
        "centropic-accent":
          "linear-gradient(90deg, #00F0FF 0%, #7000FF 100%)",
      },
      fontFamily: {
        sans: [
          '"Plus Jakarta Sans"',
          "Inter",
          "Geist",
          "system-ui",
          "sans-serif",
        ],
        display: [
          '"Plus Jakarta Sans"',
          "Inter",
          "Geist",
          "system-ui",
          "sans-serif",
        ],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
