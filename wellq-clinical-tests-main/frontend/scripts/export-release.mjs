import { spawnSync } from 'node:child_process'

// Compile an API-mode production bundle independently of the public demo build.
// Inputs and output are synthetic/static; no server, secret or DB provisioning.
for (const [entry, args, env] of [
  [
    'node_modules/vite/bin/vite.js',
    ['build', '--outDir', 'test-results/release'],
    { VITE_DATA_MODE: 'api' },
  ],
  [
    'node_modules/@playwright/test/cli.js',
    ['test', '--config', 'playwright.release.config.ts'],
    {},
  ],
]) {
  const result = spawnSync(process.execPath, [entry, ...args], {
    stdio: 'inherit',
    env: { ...process.env, ...env },
  })
  if (result.status !== 0) process.exit(result.status ?? 1)
}
