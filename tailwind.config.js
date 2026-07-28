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
      },
    },
  },
  plugins: [],
};
