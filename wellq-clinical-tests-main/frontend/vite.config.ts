import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { shellPwa } from './scripts/pwa-plugin.mjs'
export default defineConfig({
  plugins: [react(), shellPwa()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000' },
  },
  preview: { port: 4173, strictPort: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
