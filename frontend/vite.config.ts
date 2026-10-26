import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Flask API (matches list, state snapshots, SSE streams)
      '/api': 'http://localhost:8080',
    },
  },
})
