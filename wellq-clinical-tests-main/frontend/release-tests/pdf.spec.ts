import { test, expect } from '@playwright/test'
import { syntheticReport, syntheticSeries } from '../src/test/records'

test('compiled production API portal retains report reads but blocks PDF export despite granted capability', async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.wellqIdentity = {
      getSession: async () => ({
        accessToken: 'synthetic-release-session',
        role: 'clinician',
        resourceId: 'synthetic-clinician',
        tenantId: 'synthetic-tenant',
        permissions: ['clinical:read', 'reports:export'],
        capabilities: ['report_export'],
        expiresAt: Math.floor(Date.now() / 1000) + 900,
      }),
    }
  })
  let exports = 0,
    reports = 0
  await page.route('**/health', (r) => r.fulfill({ json: { status: 'ok' } }))
  await page.route('**/api/v1/**', (r) => {
    const path = new URL(r.request().url()).pathname
    if (path.endsWith('/export')) {
      exports++
      return r.fulfill({ status: 503, json: { detail: { code: 'TEST_EXPORT_FORBIDDEN' } } })
    }
    if (path.endsWith('/lab-report')) {
      reports++
      return r.fulfill({ json: syntheticReport() })
    }
    if (path.endsWith('/markers')) return r.fulfill({ json: syntheticSeries() })
    if (path.endsWith('/lab-score'))
      return r.fulfill({ status: 404, json: { detail: { code: 'NO_SCORE_AVAILABLE' } } })
    return r.fulfill({
      json: path.endsWith('/marker-catalog') ? [] : { items: [], next_cursor: null },
    })
  })
  await page.goto('/reports')
  await page.getByLabel('ID del paciente autorizado', { exact: true }).fill('synthetic-patient')
  await page.getByRole('button', { name: 'Consultar paciente', exact: true }).click()
  await expect(page.getByText('SYNTHETIC RECORD ONLY', { exact: true })).toBeVisible()
  await expect(
    page.getByText(
      'La exportación PDF no está habilitada para uso productivo. Puedes consultar el reporte clínico en pantalla.',
      { exact: true },
    ),
  ).toBeVisible()
  const generate = page.getByRole('button', { name: 'Generar PDF', exact: true })
  await expect(generate).toBeDisabled()
  await expect(
    page.getByRole('button', { name: 'Descargar PDF verificado', exact: true }),
  ).toBeDisabled()
  await generate.evaluate((button) => (button as HTMLButtonElement).click())
  expect(reports).toBeGreaterThan(0)
  expect(exports).toBe(0)
})
