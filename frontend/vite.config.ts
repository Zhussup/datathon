import { defineConfig } from "vite";

// В dev API ходит через прокси на локальный backend (без CORS);
// в проде фронт отдают с того же хоста, что и API.
export default defineConfig({
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});