import { createHash } from 'node:crypto'
import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import { test, expect } from './fixtures'
import { syntheticReport, syntheticSeries, syntheticScores } from '../src/test/records'

async function setup(
  page: Page,
  options: { export?: boolean; role?: 'patient' | 'clinician' } = {},
) {
  await page.addInitScript(
    ({ allow, role }) => {
      let revoked = false
      window.wellqIdentity = {
        getSession: async () =>
          revoked
            ? null
            : {
                accessToken: 'synthetic-records-session',
                role,
                resourceId: role === 'patient' ? 'synthetic-patient' : 'synthetic-clinician',
                tenantId: 'synthetic-tenant',
                permissions: ['clinical:read', ...(allow ? ['reports:export'] : [])],
                capabilities: allow ? ['report_export'] : [],
                expiresAt: Math.floor(Date.now() / 1000) + 900,
              },
        subscribe: (fn) => {
          const change = () => {
            revoked = true
            fn()
          }
          window.addEventListener('records-revoke', change)
          return () => window.removeEventListener('records-revoke', change)
        },
      }
    },
    { allow: options.export !== false, role: options.role || 'clinician' },
  )
  const pdf = Buffer.from('%PDF-1.4\nSYNTHETIC TEST BYTES ONLY\n%%EOF')
  const controls = {
    offline: false,
    status: 0,
    signer: false,
    expired: false,
    score: false,
    blocked: false,
    changed: false,
    delay: 0,
    mixed: false,
    empty: false,
    exports: [] as { key: string; body: unknown }[],
    downloads: 0,
    bearer: false,
  }
  await page.route('**/health', (r) =>
    controls.offline
      ? r.abort('internetdisconnected')
      : r.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' }),
  )
  await page.route('https://storage.invalid/**', async (r) => {
    controls.downloads++
    controls.bearer ||= !!r.request().headers().authorization
    await r.fulfill({
      status: controls.expired ? 403 : 200,
      contentType: 'application/pdf',
      body: pdf,
    })
  })
  await page.route('**/api/v1/**', async (r) => {
    if (controls.offline) {
      await r.abort('internetdisconnected')
      return
    }
    const url = new URL(r.request().url()),
      patient = url.pathname.split('/')[4] || 'synthetic-patient'
    let status = 200,
      body: unknown
    if (
      controls.blocked ||
      (url.pathname.includes('/patients/') && patient !== 'synthetic-patient')
    ) {
      status = 403
      body = { detail: { code: 'FORBIDDEN' } }
    } else if (url.pathname.endsWith('/export')) {
      controls.exports.push({
        key: r.request().headers()['idempotency-key']!,
        body: r.request().postDataJSON(),
      })
      if (controls.delay) await new Promise((resolve) => setTimeout(resolve, controls.delay))
      if (controls.status) {
        status = controls.status
        controls.status = 0
        body = {
          detail: {
            code:
              status === 409
                ? 'EXPORT_SOURCE_CHANGED'
                : status === 502
                  ? 'STORAGE_ERROR'
                  : 'REQUEST_FAILED',
          },
        }
      } else
        body = {
          export_id: 'synthetic-export',
          patient_id: 'synthetic-patient',
          status: controls.signer ? 'download_pending' : 'ready',
          download_url: controls.signer ? null : 'https://storage.invalid/synthetic-report',
          expires_at: controls.signer ? null : new Date(Date.now() + 300000).toISOString(),
          file_name: 'synthetic-report.pdf',
          size_bytes: pdf.length,
          sha256: createHash('sha256').update(pdf).digest('hex'),
          storage: 'gcs',
          replayed: controls.exports.length > 1,
          generated_at: '2026-11-01T12:00:00Z',
        }
    } else if (url.pathname.endsWith('/lab-report')) {
      const report = syntheticReport()
      if (controls.changed) report.header.exams[0]!.title = 'SYNTHETIC CHANGED SOURCE'
      body = report
    } else if (url.pathname.endsWith('/lab-score')) {
      if (controls.score) body = syntheticScores()
      else {
        status = 404
        body = { detail: { code: 'NO_SCORE_AVAILABLE', reason: 'insufficient_coverage' } }
      }
    } else if (url.pathname.endsWith('/markers')) {
      const series = syntheticSeries()
      if (controls.mixed)
        series.series[0]!.points.push({
          ...series.series[0]!.points[0]!,
          measured_on: '2026-04-01',
          value: 5,
          unit: 'mmol/L',
          reference: { low: 3.9, high: 6.1, unit: 'mmol/L', source: 'document' },
        })
      if (controls.empty) series.series[0]!.points = []
      body = series
    } else if (url.pathname.endsWith('/marker-catalog'))
      body = [
        {
          marker_code: 'glucose',
          name: 'Synthetic glucose',
          panel_code: 'metabolic',
          canonical_unit: 'mg/dL',
          clinically_validated: false,
        },
      ]
    else body = { items: [], next_cursor: null }
    await r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto('http://127.0.0.1:5174/history')
  if (options.role !== 'patient') {
    await page.getByLabel('ID del paciente autorizado', { exact: true }).fill('synthetic-patient')
    await page.getByRole('button', { name: 'Consultar paciente', exact: true }).click()
    await expect(
      page.getByRole('table', { name: 'Mediciones recibidas de la API, en orden cronológico' }),
    ).toBeVisible()
  }
  return controls
}
async function report(page: Page) {
  await page.locator('main').getByRole('link', { name: 'Reportes', exact: true }).click()
  await expect(page.getByText('SYNTHETIC RECORD ONLY', { exact: true })).toBeVisible()
}
for (const width of [320, 360, 375, 390, 430, 768, 1024, 1280, 1440, 1920])
  test(`clinical records and report responsive at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const controls = await setup(page)
    await expect(
      page.getByText('No hay un puntaje vigente publicable disponible.', { exact: false }),
    ).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page
      .getByRole('combobox', { name: 'Inspeccionar una medición', exact: true })
      .selectOption('1')
    await expect(page.getByRole('status').filter({ hasText: '2026-02-01 · 98' })).toBeVisible()
    const chart = page.getByRole('application').first()
    await chart.focus()
    await page.keyboard.press('ArrowRight')
    if (width === 320) {
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
            .analyze()
        ).violations,
      ).toEqual([])
    }
    await report(page)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    if (width === 320) {
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
            .analyze()
        ).violations,
      ).toEqual([])
    }
    if ([320, 768, 1440].includes(width))
      await page.screenshot({ path: `test-results/records-report-${width}.png`, fullPage: true })
    const button = page.getByRole('button', { name: 'Generar PDF', exact: true })
    await button.evaluate((b) => {
      ;(b as HTMLButtonElement).click()
      ;(b as HTMLButtonElement).click()
    })
    await expect(
      page.getByRole('button', { name: 'Descargar PDF verificado', exact: true }),
    ).toBeEnabled()
    expect(controls.exports).toHaveLength(1)
    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Descargar PDF verificado', exact: true }).click()
    expect((await download).suggestedFilename()).toBe('synthetic-report.pdf')
    await expect(
      page.getByText('PDF verificado y entregado al navegador para guardar.', { exact: true }),
    ).toBeVisible()
    expect(controls.downloads).toBe(1)
    expect(controls.bearer).toBe(false)
  })
test('patient role has neither clinical navigation nor records access', async ({ page }) => {
  await setup(page, { role: 'patient' })
  await expect(
    page.getByRole('heading', { name: 'Esta vista no está disponible para tu rol.' }),
  ).toBeVisible()
  await expect(page.getByRole('link', { name: 'Reportes', exact: true })).toHaveCount(0)
})
test('read access without export grants cannot generate a PDF', async ({ page }) => {
  const controls = await setup(page, { export: false })
  await report(page)
  await expect(page.getByRole('button', { name: 'Generar PDF', exact: true })).toBeDisabled()
  expect(controls.exports).toHaveLength(0)
})
test('offline keeps prior measurements, renews reads without replay and erases data on patient or identity change', async ({
  page,
  context,
}) => {
  const controls = await setup(page)
  await page.getByLabel('Desde', { exact: true }).fill('2026-01-01')
  controls.offline = true
  await context.setOffline(true)
  await page.evaluate(() => window.dispatchEvent(new Event('offline')))
  await expect(page.getByRole('table')).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Actualizar datos clínicos', exact: true }),
  ).toBeDisabled()
  await expect(page.getByLabel('Desde', { exact: true })).toHaveValue('2026-01-01')
  controls.offline = false
  await context.setOffline(false)
  await expect(
    page.getByRole('button', { name: 'Actualizar datos clínicos', exact: true }),
  ).toBeEnabled()
  expect(controls.exports).toHaveLength(0)
  await page
    .getByLabel('ID del paciente autorizado', { exact: true })
    .fill('synthetic-other-patient')
  await page.getByRole('button', { name: 'Consultar paciente', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'El acceso clínico ya no está disponible' }),
  ).toBeVisible()
  await expect(page.getByRole('table')).toHaveCount(0)
  await page.evaluate(() => window.dispatchEvent(new Event('records-revoke')))
  await expect(page.getByRole('table')).toHaveCount(0)
})
test('pending signer and storage failure retain the same request key; a stale report blocks downloads', async ({
  page,
}) => {
  const controls = await setup(page)
  await report(page)
  controls.signer = true
  await page.getByRole('button', { name: 'Generar PDF', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('no pudo emitir')
  await expect(
    page.getByRole('button', { name: 'Descargar PDF verificado', exact: true }),
  ).toBeDisabled()
  controls.signer = false
  await page
    .getByRole('button', { name: 'Reintentar la misma exportación / renovar enlace', exact: true })
    .click()
  await expect(
    page.getByRole('button', { name: 'Descargar PDF verificado', exact: true }),
  ).toBeEnabled()
  expect(controls.exports[0]!.key).toBe(controls.exports[1]!.key)
  controls.changed = true
  await page.getByRole('button', { name: 'Descargar PDF verificado', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('fuente del reporte cambió')
  expect(controls.downloads).toBe(0)
})
test('expired signed URL is renewed explicitly; revocation rejects a delayed export response', async ({
  page,
}) => {
  const controls = await setup(page)
  await report(page)
  await page.getByRole('button', { name: 'Generar PDF', exact: true }).click()
  await expect(
    page.getByRole('button', { name: 'Descargar PDF verificado', exact: true }),
  ).toBeEnabled()
  controls.expired = true
  await page.getByRole('button', { name: 'Descargar PDF verificado', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('caducó')
  controls.expired = false
  controls.delay = 1200
  await page
    .getByRole('button', { name: 'Reintentar la misma exportación / renovar enlace', exact: true })
    .click()
  await expect.poll(() => controls.exports.length).toBe(2)
  await page.evaluate(() => window.dispatchEvent(new Event('records-revoke')))
  await expect(
    page.getByRole('button', { name: 'Descargar PDF verificado', exact: true }),
  ).toHaveCount(0)
})
test('authorized zero scores, dark English, touch and keyboard remain accessible', async ({
  page,
}) => {
  await page.setViewportSize({ width: 640, height: 420 })
  const controls = await setup(page)
  controls.score = true
  await page.getByRole('button', { name: 'Actualizar datos clínicos', exact: true }).click()
  await expect(page.getByText('0', { exact: true }).first()).toBeVisible()
  await page.getByLabel('Idioma', { exact: true }).selectOption('en')
  await page.getByRole('button', { name: 'Dark theme', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Clinical history and trends' })).toBeVisible()
  await page.getByRole('combobox', { name: 'Inspect a measurement', exact: true }).focus()
  await page.keyboard.press('ArrowDown')
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze()
    ).violations,
  ).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('incompatible units are separate charts and empty series never retain invented measurements', async ({
  page,
}) => {
  const controls = await setup(page)
  controls.mixed = true
  await page.getByRole('button', { name: 'Actualizar datos clínicos', exact: true }).click()
  await expect(page.getByRole('application')).toHaveCount(2)
  await expect(
    page.getByText('Solo hay una medición. No se puede establecer una tendencia.', { exact: true }),
  ).toBeVisible()
  controls.empty = true
  await page.getByRole('button', { name: 'Actualizar datos clínicos', exact: true }).click()
  await expect(
    page.getByText('No se recibieron mediciones confirmadas para esta selección.', { exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('application')).toHaveCount(0)
  await expect(page.getByRole('table')).toHaveCount(0)
})
test('storage failure is visible and recovery requires explicit same-key export', async ({
  page,
}) => {
  const controls = await setup(page)
  await report(page)
  controls.status = 502
  await page.getByRole('button', { name: 'Generar PDF', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('almacenamiento')
  await page.getByRole('button', { name: 'Comprobar conexión', exact: true }).click()
  const retry = page.getByRole('button', {
    name: 'Reintentar la misma exportación / renovar enlace',
    exact: true,
  })
  await expect(retry).toBeEnabled()
  expect(controls.exports).toHaveLength(1)
  await retry.click()
  await expect(
    page.getByRole('button', { name: 'Descargar PDF verificado', exact: true }),
  ).toBeEnabled()
  expect(controls.exports[0]!.key).toBe(controls.exports[1]!.key)
})

test('touch landscape and 200 percent equivalent reflow retain accessible clinical details', async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 640, height: 420 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  })
  const page = await context.newPage()
  try {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await setup(page)
    await page
      .getByRole('combobox', { name: 'Inspeccionar una medici\u00f3n', exact: true })
      .selectOption('0')
    await expect(page.getByRole('status').filter({ hasText: '2026-01-01' })).toBeVisible()
    await page.locator('main').getByRole('link', { name: 'Reportes', exact: true }).tap()
    await expect(page.getByText('SYNTHETIC RECORD ONLY', { exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
          .analyze()
      ).violations,
    ).toEqual([])
  } finally {
    await context.close()
  }
})
