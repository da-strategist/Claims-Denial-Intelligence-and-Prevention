import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.js",
  },
  server: {
    port: 5174,
    proxy: {
      "/api": {
        // API_TARGET points a second dev server at another backend (e.g. a scratch copy)
        target: process.env.API_TARGET || "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});
