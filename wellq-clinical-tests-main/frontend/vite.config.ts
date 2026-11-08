import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { shellPwa } from './scripts/pwa-plugin.mjs'
import { localIdentity } from './scripts/local-identity.mjs'
const proxyTarget = process.env.WELLQ_DEV_API_TARGET || 'http://127.0.0.1:8000'
const proxyUrl = new URL(proxyTarget)
if (
  proxyUrl.username ||
  proxyUrl.password ||
  proxyUrl.search ||
  proxyUrl.hash ||
  !['http:', 'https:'].includes(proxyUrl.protocol) ||
  (proxyUrl.protocol === 'http:' &&
    !['127.0.0.1', 'localhost', '[::1]'].includes(proxyUrl.hostname))
)
  throw new Error('Invalid API proxy target')
export default defineConfig({
  plugins: [
    react(),
    shellPwa(),
    ...(process.env.WELLQ_LOCAL_INTEGRATION === '1' ? [localIdentity()] : []),
  ],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': proxyTarget,
      '/health': proxyTarget,
      '/ready': proxyTarget,
      ...(process.env.WELLQ_LOCAL_INTEGRATION === '1' ? { '/__wellq_local': proxyTarget } : {}),
    },
  },
  preview: { port: 4173, strictPort: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
