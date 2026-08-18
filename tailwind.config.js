/** @type {import('tailwindcss').Config} */
/** Logo Chrome tokens — keep in sync with static/css/app.css + BRAND.md */
module.exports = {
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
          cyan: "#C9D3DD", // Chrome silver (primary accent)
          blue: "#5B6B7A", // Steel shadow (secondary)
          violet: "#5B6B7A", // Legacy name → steel (never purple)
          muted: "#8B97A8",
        },
      },
      boxShadow: {
        glow: "0 12px 28px rgba(0, 0, 0, 0.35)",
        "glow-violet": "0 12px 28px rgba(0, 0, 0, 0.3)",
        "glow-holo": "0 16px 40px rgba(0, 0, 0, 0.45)",
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
