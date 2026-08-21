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
          bg: "#121212",
          card: "#1A1612",
          border: "#3A2E22",
          cyan: "#E8A04A", // Warm gold (primary accent)
          blue: "#C47A2C",
          violet: "#C47A2C", // Legacy name — never purple
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
      fontFamily: {
        display: ['"Inter"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
