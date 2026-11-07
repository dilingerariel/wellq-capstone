import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './release-tests',
  outputDir: 'test-results/release-browser',
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:4174', channel: 'msedge', headless: true },
  webServer: {
    command: 'npm.cmd run preview -- --outDir test-results/release --port 4174',
    url: 'http://127.0.0.1:4174',
    reuseExistingServer: false,
  },
})
