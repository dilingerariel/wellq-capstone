import { defineConfig } from '@playwright/test'
if (!process.env.WELLQ_HTTP_FIXTURE || !process.env.WELLQ_DEV_API_TARGET)
  throw new Error('Run npm run test:live with the guarded isolated integration harness')
export default defineConfig({
  timeout: 60_000,
  expect: { timeout: 15_000 },
  testDir: './live-tests',
  workers: 1,
  retries: 0,
  reporter: [['list']],
  outputDir: 'test-results/live',
  use: {
    baseURL: 'http://127.0.0.1:5175',
    channel: 'msedge',
    headless: true,
    trace: 'off',
    video: 'off',
    screenshot: 'off',
  },
  webServer: {
    command: 'npm.cmd run dev -- --port 5175 --strictPort',
    url: 'http://127.0.0.1:5175',
    reuseExistingServer: false,
    env: {
      VITE_DATA_MODE: 'api',
      VITE_API_BASE_URL: '/api/v1',
      VITE_API_HEALTH_URL: '/health',
      WELLQ_DEV_API_TARGET: process.env.WELLQ_DEV_API_TARGET,
    },
  },
})
