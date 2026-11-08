import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './local-tests',
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  outputDir: 'test-results/local',
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5178',
    channel: 'msedge',
    headless: true,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
})
