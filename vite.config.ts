import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ command }) => ({
  plugins: [react()],
  // Production assets are served from Flask's /static/geo-ui/
  base: command === "build" ? "/static/geo-ui/" : "/",
  resolve: {
    alias: {
      "@": rootDir,
    },
  },
  build: {
    outDir: "static/geo-ui",
    emptyOutDir: true,
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          recharts: ["recharts"],
        },
      },
    },
  },
  server: {
    port: 5173,
    open: false,
  },
}));
