import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // On Vercel the app is served from root — remove the /app/ sub-path
  base: '/',
  build: {
    // Output into iars-react/dist — Vercel reads outputDirectory from vercel.json
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    open: true,
    proxy: {
      // In local dev, proxy /api requests to the FastAPI server
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
