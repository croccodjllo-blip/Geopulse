/** @type {import('tailwindcss').Config} */
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
          bg: "#080B10",
          card: "#121824",
          border: "#1F2937",
          cyan: "#00F0FF",
          blue: "#0066FF",
          violet: "#8A2BE2",
          muted: "#94A3B8",
        },
      },
      boxShadow: {
        glow: "0 0 15px rgba(0, 240, 255, 0.15)",
        "glow-violet": "0 0 15px rgba(138, 43, 226, 0.25)",
        "glow-holo":
          "0 0 24px rgba(0, 240, 255, 0.35), 0 0 48px rgba(138, 43, 226, 0.18)",
      },
    },
  },
  plugins: [],
};
