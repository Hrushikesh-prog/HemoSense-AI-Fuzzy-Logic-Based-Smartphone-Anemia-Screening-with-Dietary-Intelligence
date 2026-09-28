import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, /api/* is proxied to the FastAPI server so no CORS setup is needed.
// Override the target with HEMOSENSE_API_TARGET, or skip the proxy entirely by
// setting VITE_API_URL (see .env.example).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      '/api': {
        target: process.env.HEMOSENSE_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
