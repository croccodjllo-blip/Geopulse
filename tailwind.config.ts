import type { Config } from "tailwindcss";

/** Logo Chrome — mirrors tailwind.config.js (no Nova Violet / neon). */
const config: Config = {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: "#04060A",
          card: "#0A0E14",
          border: "#1A222D",
          cyan: "#C9D3DD",
          blue: "#5B6B7A",
          violet: "#5B6B7A", // legacy alias → steel (never purple)
          steel: "#5B6B7A",
          muted: "#8B97A8",
        },
      },
      boxShadow: {
        glow: "0 12px 28px rgba(0, 0, 0, 0.35)",
        "glow-steel": "0 12px 28px rgba(0, 0, 0, 0.3)",
        "glow-violet": "0 12px 28px rgba(0, 0, 0, 0.3)", // legacy alias
        "glow-holo": "0 16px 40px rgba(0, 0, 0, 0.45)",
      },
      backgroundImage: {
        "liquid-chrome":
          "linear-gradient(165deg, #04060A 0%, #070A10 48%, #0A0E14 100%)",
        iridescent:
          "linear-gradient(90deg, #5B6B7A 0%, #C9D3DD 55%, #D7DEE5 100%)",
      },
      fontFamily: {
        display: ['"Inter"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
