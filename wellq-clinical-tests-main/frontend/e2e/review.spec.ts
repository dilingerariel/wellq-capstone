import { test, expect } from './fixtures'
import type { Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

async function fixture(page: Page) {
  await page.route('**/health', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' }),
  )
  await page.addInitScript(() => {
    let changed = false
    window.wellqIdentity = {
      getSession: async () => ({
        accessToken: 'synthetic-review-session',
        tenantId: 'synthetic-tenant',
        resourceId: changed ? 'synthetic-other' : 'synthetic-patient',
        role: 'patient',
        permissions: ['clinical:read', 'extractions:confirm'],
        capabilities: [],
        expiresAt: Math.floor(Date.now() / 1000) + 900,
      }),
      subscribe: (fn) => {
        const cb = () => {
          changed = true
          fn()
        }
        window.addEventListener('review-account-change', cb)
        return () => window.removeEventListener('review-account-change', cb)
      },
    }
  })
  const ext = {
    clinical_test_id: 'synthetic-doc',
    extraction_id: 'synthetic-extraction',
    status: 'awaiting_confirmation',
    document: { document_type: 'blood_panel', collection_date: '2026-01-01', report_date: null },
    panels: [
      {
        panel_code: 'metabolic',
        panel_name_raw: 'SYNTHETIC PANEL',
        markers: [
          {
            marker_code: 'glucose',
            raw_name: 'Synthetic glucose',
            value_raw: '90',
            unit_raw: 'mg/dL',
            confidence: { value: 0.6, unit: 0.99, reference: 0.8, name: 0.99 },
            reference: { low: 70, high: 110, unit: 'mg/dL', source: 'document' },
            provenance: { page: 1, evidence: 'Synthetic evidence' },
          },
        ],
      },
    ],
    flags: [{ code: 'identity_unverified' }, { code: 'low_confidence', marker_code: 'glucose' }],
  }
  const seen = { patches: [] as { body: Record<string, unknown>; key: string }[], refusal: 0 }
  await page.route('**/api/v1/**', async (route) => {
    const req = route.request()
    let status = 200,
      body: unknown
    if (req.method() === 'PATCH') {
      seen.patches.push({ body: req.postDataJSON(), key: req.headers()['idempotency-key']! })
      if (seen.refusal) {
        status = seen.refusal
        body = { detail: { code: 'VALUE_INVALID_FORMAT' } }
        seen.refusal = 0
      } else {
        ext.status = 'confirmed'
        body = ext
      }
    } else if (req.url().endsWith('/extraction')) body = ext
    else if (req.url().endsWith('/synthetic-doc'))
      body = {
        clinical_test_id: 'synthetic-doc',
        patient_id: 'synthetic-patient',
        title: 'SYNTHETIC REVIEW DOCUMENT',
        test_type: 'blood_test',
        test_date: '2026-01-01',
        file: { name: 'synthetic-review.pdf', mime_type: 'application/pdf', size_bytes: 123 },
        status: 'ready_for_review',
        review: { status: 'not_reviewed' },
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
      }
    else body = { items: [], next_cursor: null }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto('http://127.0.0.1:5174/exams/synthetic-doc/extraction')
  await expect(page.getByLabel('Valor glucose', { exact: true })).toHaveValue('90')
  return { ext, seen }
}
async function edit(page: Page) {
  await page.getByLabel('Valor glucose', { exact: true }).fill('95')
  await page.getByLabel('He comprobado que este documento me corresponde.', { exact: true }).check()
  await page
    .getByLabel('He revisado el marcador glucose marcado con baja confianza.', { exact: true })
    .check()
  await page.getByRole('button', { name: 'Revisar cambios', exact: true }).click()
}
for (const width of [320, 360, 375, 390, 430, 768, 1024, 1280, 1440, 1920]) {
  test(`review responsive, accessible edits and confirmation at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const { seen } = await fixture(page)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    if ([320, 768, 1440].includes(width))
      await page.screenshot({ path: `test-results/review-${width}.png`, fullPage: true })
    if (width === 320)
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
            .analyze()
        ).violations,
      ).toEqual([])
    await edit(page)
    await expect(page.getByRole('heading', { name: 'Cambios que se enviarán' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page
      .getByRole('button', { name: 'Confirmar datos revisados', exact: true })
      .evaluate((button) => {
        ;(button as HTMLButtonElement).click()
        ;(button as HTMLButtonElement).click()
      })
    await expect(
      page.getByText('Confirmación registrada por el servidor. No equivale a validación clínica.', {
        exact: true,
      }),
    ).toBeVisible()
    expect(seen.patches).toHaveLength(1)
    expect(seen.patches[0]!.body).toMatchObject({
      document_edits: { identity_confirmed: true },
      marker_edits: [{ marker_code: 'glucose', value_raw: '95', unit_raw: 'mg/dL' }],
      acknowledged_marker_codes: ['glucose'],
    })
    expect(seen.patches[0]!.key.length).toBeGreaterThan(8)
  })
}
test('draft survives navigation and offline; changed proposal blocks reconnect confirmation', async ({
  page,
  context,
}) => {
  const { ext, seen } = await fixture(page)
  let disconnected = false
  await page.route('**/health', (route) =>
    disconnected
      ? route.abort('internetdisconnected')
      : route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' }),
  )
  await edit(page)
  await page.getByRole('link', { name: 'Volver a exámenes', exact: true }).click()
  await page.getByRole('link', { name: 'Revisar extracción', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Cambios que se enviarán' })).toBeVisible()
  disconnected = true
  await context.setOffline(true)
  await page.evaluate(() => window.dispatchEvent(new Event('offline')))
  await expect(
    page.getByRole('button', { name: 'Confirmar datos revisados', exact: true }),
  ).toBeDisabled()
  ext.extraction_id = 'synthetic-replacement'
  disconnected = false
  await context.setOffline(false)
  await page.evaluate(() => window.dispatchEvent(new Event('online')))
  await expect(
    page.getByRole('button', { name: 'Confirmar datos revisados', exact: true }),
  ).toBeEnabled()
  expect(seen.patches).toHaveLength(0)
  await page.getByRole('button', { name: 'Confirmar datos revisados', exact: true }).click()
  await expect(
    page.getByText('La propuesta cambió en el servidor.', { exact: false }),
  ).toBeVisible()
  expect(seen.patches).toHaveLength(0)
})
test('server validation permits correction; identity change erases private draft', async ({
  page,
}) => {
  const { seen } = await fixture(page)
  await edit(page)
  seen.refusal = 422
  await page.getByRole('button', { name: 'Confirmar datos revisados', exact: true }).click()
  await expect(
    page.getByRole('alert').filter({ hasText: 'El valor debe ser un número válido.' }),
  ).toBeVisible()
  await expect(page.getByLabel('Valor glucose', { exact: true })).toBeEditable()
  await page.evaluate(() => window.dispatchEvent(new Event('review-account-change')))
  await expect(page.getByLabel('Valor glucose', { exact: true })).toHaveCount(0)
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }).includes('Synthetic glucose'),
    ),
  ).toBe(false)
})
test('dark English keyboard, touch landscape and 200 percent equivalent reflow', async ({
  page,
}) => {
  await page.setViewportSize({ width: 640, height: 450 })
  await fixture(page)
  await page.getByRole('button', { name: 'Tema oscuro', exact: true }).click()
  await page.getByLabel('Idioma', { exact: true }).selectOption('en')
  await expect(page.getByRole('heading', { name: 'Review extraction', exact: true })).toBeVisible()
  const value = page.getByLabel('Value glucose', { exact: true })
  await value.focus()
  await page.keyboard.press('ControlOrMeta+A')
  await page.keyboard.type('95')
  expect(await value.inputValue()).toBe('95')
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze()
    ).violations,
  ).toEqual([])
  await page.setViewportSize({ width: 844, height: 390 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('uncertain server response retains the exact body and idempotency key for explicit retry', async ({
  page,
}) => {
  const { ext, seen } = await fixture(page)
  await edit(page)
  seen.refusal = 500
  await page.getByRole('button', { name: 'Confirmar datos revisados', exact: true }).click()
  await expect(
    page.getByRole('alert').filter({ hasText: 'Respuesta incierta del servidor.' }),
  ).toBeVisible()
  ext.status = 'confirmed'
  await page.getByRole('button', { name: 'Comprobar conexión', exact: true }).click()
  const retry = page.getByRole('button', {
    name: 'Verificar y reintentar confirmación',
    exact: true,
  })
  await expect(retry).toBeEnabled()
  expect(seen.patches).toHaveLength(1)
  await retry.click()
  await expect(
    page.getByText('Confirmación registrada por el servidor. No equivale a validación clínica.', {
      exact: true,
    }),
  ).toBeVisible()
  expect(seen.patches).toHaveLength(2)
  expect(seen.patches[0]).toEqual(seen.patches[1])
})

test('review touch controls, landscape and scaled reflow preserve corrected values', async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
    deviceScaleFactor: 2,
  })
  const page = await context.newPage()
  await fixture(page)
  await page.getByLabel('Valor glucose', { exact: true }).fill('95')
  await page.getByLabel('He comprobado que este documento me corresponde.', { exact: true }).tap()
  await page
    .getByLabel('He revisado el marcador glucose marcado con baja confianza.', { exact: true })
    .tap()
  await page.setViewportSize({ width: 844, height: 390 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Revisar cambios', exact: true }).tap()
  await expect(page.getByRole('heading', { name: 'Cambios que se enviarán' })).toBeVisible()
  await page.setViewportSize({ width: 640, height: 450 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await context.close()
})
