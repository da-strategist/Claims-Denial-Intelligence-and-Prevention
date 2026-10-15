import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Forward /api/* to the FastAPI backend so the app can use relative URLs
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
