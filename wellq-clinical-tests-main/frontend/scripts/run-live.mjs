import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
const local = fileURLToPath(
  new URL(
    '../../../.venv/' + (process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'),
    import.meta.url,
  ),
)
const python = process.env.WELLQ_TEST_PYTHON || (existsSync(local) ? local : 'python')
const result = spawnSync(python, [fileURLToPath(new URL('./live_api.py', import.meta.url))], {
  stdio: 'inherit',
  env: process.env,
})
process.exit(result.status ?? 1)
