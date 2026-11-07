import { readFileSync, writeFileSync } from 'node:fs'
import { test, expect } from './fixtures'

test('a waiting shell update needs approval and cancellation keeps the current in-memory form', async ({
  page,
}) => {
  const worker = readFileSync('dist/sw.js', 'utf8')
  writeFileSync(
    'dist/sw-update-test.js',
    worker.replace(/wellq-shell-[0-9a-f]+/, 'wellq-shell-synthetic-update-test'),
  )
  await page.goto('http://127.0.0.1:4173/exams')
  await expect(page.getByRole('heading', { name: 'Exámenes médicos' })).toBeVisible()
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
    if (!navigator.serviceWorker.controller)
      await new Promise<void>((resolve) =>
        navigator.serviceWorker.addEventListener('controllerchange', () => resolve(), {
          once: true,
        }),
      )
    await caches.open('unrelated-synthetic-public-cache')
  })
  await page.getByLabel('Estado del documento', { exact: true }).selectOption('processing')
  await page.evaluate(async () => {
    await navigator.serviceWorker.register('/sw-update-test.js', { scope: '/' })
  })
  const update = page.getByRole('button', { name: 'Actualizar portal', exact: true })
  await expect(update).toBeVisible()
  expect(await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL)).toMatch(
    /\/sw\.js$/,
  )
  page.once('dialog', (dialog) => dialog.dismiss())
  await update.click()
  await expect(page.getByLabel('Estado del documento', { exact: true })).toHaveValue('processing')
  await expect(update).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await Promise.all([
    page.waitForEvent('framenavigated', (frame) => frame === page.mainFrame()),
    update.click(),
  ])
  await page.waitForLoadState('domcontentloaded')
  await expect
    .poll(() => page.evaluate(() => navigator.serviceWorker.controller?.scriptURL))
    .toMatch(/\/sw-update-test\.js$/)
  await expect(page.getByRole('heading', { name: 'Exámenes médicos' })).toBeVisible()
  await expect(page.getByLabel('Estado del documento', { exact: true })).toHaveValue('')
  expect(await page.evaluate(() => caches.keys())).toContain('unrelated-synthetic-public-cache')
})
