import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    channel: 'msedge',
    headless: true,
    trace: 'retain-on-failure',
  },
  webServer: [
    { command: 'npm.cmd run preview', url: 'http://127.0.0.1:4173', reuseExistingServer: false },
    {
      command: 'npm.cmd run dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      env: { VITE_DATA_MODE: 'demo' },
    },
    {
      command: 'npm.cmd run dev -- --port 5174',
      url: 'http://127.0.0.1:5174',
      reuseExistingServer: false,
      env: { VITE_DATA_MODE: 'api' },
    },
  ],
})
