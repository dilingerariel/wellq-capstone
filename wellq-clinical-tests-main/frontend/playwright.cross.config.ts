import { defineConfig } from '@playwright/test'

// No webServer hook: the isolated orchestrator starts only its own Vite.
export default defineConfig({
  testDir: './e2e',
  testMatch: 'cross-client.spec.ts',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 120_000,
  reporter: [['list']],
  use: {
    channel: 'msedge',
    headless: true,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
})
