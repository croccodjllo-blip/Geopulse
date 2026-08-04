import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    // Flask shell still ships the live dashboard UI
    "./templates/**/*.html",
    "./static/js/**/*.{js,ts}",
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
      },
      boxShadow: {
        glow: "0 0 15px rgba(0, 240, 255, 0.15)",
        "glow-violet": "0 0 15px rgba(112, 0, 255, 0.2)",
      },
    },
  },
  plugins: [],
};

export default config;
