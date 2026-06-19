import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: proxy /api → the read-only FastAPI snapshot service so the browser only ever talks to Vite
// (same-origin in dev, no CORS), and the API stays bound to localhost. Override target via DRAMATIC_API.
export default defineConfig({
  plugins: [react()],
  server: {
    // Accessed over the trusted tailnet (bind via --host); allow the .ts.net Host header (Vite's
    // rebind guard blocks unknown domains by default — IP literals are allowed already).
    allowedHosts: [".tail57521e.ts.net"],
    proxy: {
      "/api": { target: process.env.DRAMATIC_API ?? "http://127.0.0.1:8503", changeOrigin: true },
    },
  },
});
