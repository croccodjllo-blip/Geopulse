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
          bg: "#121212",
          card: "#1A1612",
          border: "#3A2E22",
          cyan: "#E8A04A",
          blue: "#C47A2C",
          violet: "#C47A2C", // legacy alias — never purple
          steel: "#C47A2C",
          muted: "#B8A894",
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
          "linear-gradient(165deg, #121212 0%, #161310 48%, #1A1612 100%)",
        iridescent:
          "linear-gradient(90deg, #8A4E16 0%, #E8A04A 55%, #F4D7A8 100%)",
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
