import type { Config } from "tailwindcss";

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
          bg: "#080B10", // Liquid chrome carbon
          card: "#121824", // Metallic carbon
          border: "#1F2937",
          cyan: "#00F0FF", // Neon Electric Cyan
          blue: "#0066FF", // Quantum Blue
          violet: "#8A2BE2", // Holographic Violet / UV
          muted: "#94A3B8",
        },
      },
      boxShadow: {
        glow: "0 0 15px rgba(0, 240, 255, 0.15)",
        "glow-violet": "0 0 15px rgba(138, 43, 226, 0.25)",
        "glow-holo":
          "0 0 24px rgba(0, 240, 255, 0.35), 0 0 48px rgba(138, 43, 226, 0.18)",
      },
      backgroundImage: {
        "liquid-chrome":
          "radial-gradient(ellipse 70% 55% at 70% 40%, rgba(0,240,255,0.14), transparent 58%), radial-gradient(ellipse 55% 45% at 20% 70%, rgba(138,43,226,0.16), transparent 55%), linear-gradient(165deg, #080B10 0%, #0C1220 45%, #121824 100%)",
        "iridescent":
          "linear-gradient(90deg, #0066FF 0%, #00F0FF 50%, #8A2BE2 100%)",
      },
      keyframes: {
        "holo-spin": {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "holo-spin": "holo-spin 28s linear infinite",
      },
    },
  },
  plugins: [],
};
export default config;
