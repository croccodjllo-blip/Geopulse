/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.{js,ts}",
  ],
  theme: {
    extend: {
  colors: {
        centropic: {
          chaos: "#0A0F24", // Blu Notte Sfondo
          core: "#00FF9D", // Verde Smeraldo Accento
          flow: "#00D2FF", // Ciano Elettrico
          clarity: "#F5F7FA", // Bianco Platino Testo
        },
        chaos: "#0A0F24",
        core: "#00FF9D",
        flow: "#00D2FF",
        clarity: "#F5F7FA",
      },
      backgroundImage: {
        "centropic-bg":
          "linear-gradient(135deg, #0A0F24 0%, #121A3A 100%)",
        "centropic-accent":
          "linear-gradient(90deg, #00D2FF 0%, #00FF9D 100%)",
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "Inter", "system-ui", "sans-serif"],
        display: ['"Syne"', '"Plus Jakarta Sans"', "sans-serif"],
      },
    },
  },
  plugins: [],
};
