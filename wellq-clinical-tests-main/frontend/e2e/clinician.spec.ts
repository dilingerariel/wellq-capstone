import { test, expect } from './fixtures'
import type { Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
test('patient cannot enter the clinician workspace', async ({ page }) => {
  await page.addInitScript(() => {
    window.wellqIdentity = {
      getSession: async () => ({
        accessToken: 'synthetic-patient-session',
        role: 'patient',
        resourceId: 'synthetic-patient',
        tenantId: 'synthetic-tenant',
        permissions: ['clinical:read'],
        capabilities: [],
        expiresAt: Math.floor(Date.now() / 1000) + 900,
      }),
    }
  })
  await page.goto('http://127.0.0.1:5174/exams/synthetic-doc/clinical-review')
  await expect(
    page.getByRole('heading', { name: 'Esta vista no está disponible para tu rol.' }),
  ).toBeVisible()
  await expect(
    page.getByRole('textbox', { name: 'Nota privada de revisión', exact: true }),
  ).toHaveCount(0)
})
async function setup(
  page: Page,
  permissions = ['clinical:read', 'clinical:review', 'extractions:validate'],
) {
  await page.addInitScript((grants) => {
    let expired = false
    window.wellqIdentity = {
      getSession: async () =>
        expired
          ? null
          : {
              accessToken: 'synthetic-clinician-session',
              role: 'clinician',
              resourceId: 'synthetic-clinician',
              tenantId: 'synthetic-tenant',
              permissions: grants,
              capabilities: [],
              expiresAt: Math.floor(Date.now() / 1000) + 900,
            },
      subscribe: (fn) => {
        const cb = () => {
          expired = true
          fn()
        }
        window.addEventListener('clinical-session-change', cb)
        return () => window.removeEventListener('clinical-session-change', cb)
      },
    }
  }, permissions)
  const doc = {
    clinical_test_id: 'synthetic-doc',
    patient_id: 'synthetic-patient',
    title: 'SYNTHETIC CLINICAL DOCUMENT',
    test_type: 'blood_test',
    test_date: '2026-01-01',
    file: { name: 'synthetic-clinical.pdf', mime_type: 'application/pdf', size_bytes: 123 },
    status: 'ready_for_review',
    review: { status: 'not_reviewed', reviewed_by: null as string | null },
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  }
  const ext = {
    clinical_test_id: 'synthetic-doc',
    extraction_id: 'synthetic-extraction',
    status: 'confirmed',
    document: {},
    panels: [
      {
        panel_code: 'metabolic',
        panel_name_raw: 'SYNTHETIC PANEL',
        markers: [
          {
            marker_code: 'glucose',
            raw_name: 'Synthetic glucose',
            value_raw: '95',
            unit_raw: 'mg/dL',
            provenance: { page: 1, evidence: 'SYNTHETIC ONLY' },
          },
        ],
      },
    ],
    flags: [{ code: 'low_confidence', marker_code: 'glucose' }],
  }
  const controls = {
    offline: false,
    fail: 0,
    review: [] as Record<string, unknown>[],
    validation: [] as Record<string, unknown>[],
    idempotency: [] as (string | undefined)[],
  }
  await page.route('**/health', (r) =>
    controls.offline
      ? r.abort('internetdisconnected')
      : r.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' }),
  )
  await page.route('**/api/v1/**', async (r) => {
    const req = r.request(),
      path = new URL(req.url()).pathname
    let body: unknown,
      status = 200
    if (controls.offline) {
      await r.abort('internetdisconnected')
      return
    }
    if (path.endsWith('/review')) {
      controls.review.push(req.postDataJSON())
      controls.idempotency.push(req.headers()['idempotency-key'])
      doc.review = { status: 'reviewed', reviewed_by: 'synthetic-clinician' }
      doc.updated_at = '2026-01-02'
      body = doc
    } else if (path.endsWith('/validate')) {
      controls.validation.push(req.postDataJSON())
      controls.idempotency.push(req.headers()['idempotency-key'])
      if (controls.fail) {
        status = controls.fail
        controls.fail = 0
        body = {
          detail: {
            code: status === 422 ? 'INVALID_MARKER_CORRECTIONS' : 'REQUEST_FAILED',
            errors: [{ marker_code: 'glucose', code: 'UNIT_NOT_SUPPORTED' }],
          },
        }
      } else {
        const b = req.postDataJSON()
        ext.status = b.validation_status === 'rejected' ? 'rejected' : 'clinically_validated'
        for (const c of b.marker_corrections || [])
          ext.panels[0]!.markers[0]!.value_raw = c.value_raw
        body = ext
      }
    } else if (path.endsWith('/extraction')) {
      if (ext.status === 'rejected') {
        status = 409
        body = { detail: { code: 'EXTRACTION_NOT_READY' } }
      } else body = ext
    } else if (path.endsWith('/synthetic-doc')) body = doc
    else body = { items: [doc], next_cursor: null }
    await r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto('http://127.0.0.1:5174/exams')
  await page.getByLabel('ID del paciente autorizado', { exact: true }).fill('synthetic-patient')
  await page.getByRole('button', { name: 'Consultar paciente', exact: true }).click()
  await page.getByRole('link', { name: doc.title, exact: true }).click()
  await page.getByRole('link', { name: 'Revisión y validación clínica', exact: true }).click()
  await expect(page.getByLabel('Valor glucose', { exact: true })).toHaveValue('95')
  return { controls, doc, ext }
}
for (const width of [320, 360, 375, 390, 430, 768, 1024, 1280, 1440, 1920])
  test(`clinical corrections, review and accessible responsive at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const { controls } = await setup(page)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    if ([320, 768, 1440].includes(width))
      await page.screenshot({ path: `test-results/clinician-${width}.png`, fullPage: true })
    if (width === 320)
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
            .analyze()
        ).violations,
      ).toEqual([])
    await page
      .getByRole('textbox', { name: 'Nota privada de revisión', exact: true })
      .fill('SYNTHETIC PRIVATE REVIEW')
    await page.getByRole('button', { name: 'Preparar revisión', exact: true }).click()
    await page
      .getByRole('button', { name: 'Confirmar revisión del documento', exact: true })
      .click()
    await expect(
      page.getByText('El servidor registró la operación.', { exact: false }),
    ).toBeVisible()
    expect(controls.review).toEqual([
      { review_status: 'reviewed', review_note: 'SYNTHETIC PRIVATE REVIEW' },
    ])
    await page.getByRole('button', { name: 'Consultar nuevamente', exact: true }).click()
    await expect(
      page.getByRole('textbox', { name: 'Nota privada de revisión', exact: true }),
    ).toBeDisabled()
    if (width === 1920) {
      await page.getByRole('button', { name: 'Preparar rechazo', exact: true }).click()
      await page.getByRole('button', { name: 'Confirmar rechazo clínico', exact: true }).click()
      await expect(page.getByText('Extracción rechazada', { exact: true })).toBeVisible()
    } else {
      await page.getByLabel('Valor glucose', { exact: true }).fill('96')
      await page
        .getByRole('textbox', { name: 'Nota clínica de validación', exact: true })
        .fill('SYNTHETIC CLINICAL NOTE')
      await page.getByRole('button', { name: 'Preparar validación', exact: true }).click()
      await page
        .getByRole('button', { name: 'Confirmar validación clínica', exact: true })
        .evaluate((b) => {
          ;(b as HTMLButtonElement).click()
          ;(b as HTMLButtonElement).click()
        })
      await expect(page.getByText('Validado por un profesional', { exact: true })).toBeVisible()
      expect(controls.validation).toMatchObject([
        {
          validation_status: 'validated',
          clinical_note: 'SYNTHETIC CLINICAL NOTE',
          marker_corrections: [{ marker_code: 'glucose', value_raw: '96', unit_raw: 'mg/dL' }],
        },
      ])
    }
    expect(controls.validation).toHaveLength(1)
    expect(controls.idempotency.every((k) => !k)).toBe(true)
  })
test('clinical draft remains offline; reconnect does not write and server conflict blocks send', async ({
  page,
  context,
}) => {
  const { controls, ext } = await setup(page)
  await page
    .getByRole('textbox', { name: 'Nota clínica de validación', exact: true })
    .fill('SYNTHETIC RAM DRAFT')
  controls.offline = true
  await context.setOffline(true)
  await page.evaluate(() => window.dispatchEvent(new Event('offline')))
  await expect(
    page.getByRole('button', { name: 'Preparar validación', exact: true }),
  ).toBeDisabled()
  await expect(
    page.getByRole('textbox', { name: 'Nota clínica de validación', exact: true }),
  ).toHaveValue('SYNTHETIC RAM DRAFT')
  controls.offline = false
  await context.setOffline(false)
  await page.evaluate(() => window.dispatchEvent(new Event('online')))
  await expect(page.getByRole('button', { name: 'Preparar validación', exact: true })).toBeEnabled()
  expect(controls.validation).toHaveLength(0)
  await page.getByRole('button', { name: 'Preparar validación', exact: true }).click()
  ext.extraction_id = 'synthetic-replacement'
  await page.getByRole('button', { name: 'Confirmar validación clínica', exact: true }).click()
  await expect(
    page.getByRole('alert').filter({ hasText: 'El estado del servidor cambió.' }),
  ).toBeVisible()
  expect(controls.validation).toHaveLength(0)
})
test('marker errors are specific; patient switch asks before clearing; expired session clears notes', async ({
  page,
}) => {
  const { controls } = await setup(page)
  await page.getByLabel('Valor glucose', { exact: true }).fill('96')
  await page
    .getByRole('textbox', { name: 'Nota clínica de validación', exact: true })
    .fill('SYNTHETIC PRIVATE DRAFT')
  controls.fail = 422
  await page.getByRole('button', { name: 'Preparar validación', exact: true }).click()
  await page.getByRole('button', { name: 'Confirmar validación clínica', exact: true }).click()
  await expect(
    page.getByRole('alert').filter({ hasText: 'Unidad no admitida por el catálogo.' }),
  ).toBeVisible()
  page.once('dialog', (dialog) => dialog.dismiss())
  await page.getByLabel('ID del paciente autorizado', { exact: true }).fill('synthetic-other')
  await page.getByRole('button', { name: 'Consultar paciente', exact: true }).click()
  await expect(
    page.getByRole('textbox', { name: 'Nota clínica de validación', exact: true }),
  ).toHaveValue('SYNTHETIC PRIVATE DRAFT')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Consultar paciente', exact: true }).click()
  await expect(
    page.getByRole('textbox', { name: 'Nota clínica de validación', exact: true }),
  ).toHaveCount(0)
  await page.evaluate(() => window.dispatchEvent(new Event('clinical-session-change')))
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }).includes('SYNTHETIC PRIVATE'),
    ),
  ).toBe(false)
})
test('clinical mutations require distinct scopes in the UI', async ({ page }) => {
  await setup(page, ['clinical:read'])
  await expect(page.getByRole('button', { name: 'Preparar revisión', exact: true })).toBeDisabled()
  await expect(
    page.getByRole('button', { name: 'Preparar validación', exact: true }),
  ).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Preparar rechazo', exact: true })).toBeDisabled()
})
test('revoked or expired clinical identity clears an active private draft', async ({ page }) => {
  await setup(page)
  await page
    .getByRole('textbox', { name: 'Nota privada de revisión', exact: true })
    .fill('SYNTHETIC PRIVATE ACTIVE DRAFT')
  await page.evaluate(() => window.dispatchEvent(new Event('clinical-session-change')))
  await expect(
    page.getByRole('textbox', { name: 'Nota privada de revisión', exact: true }),
  ).toHaveCount(0)
  await expect(page.getByText('SYNTHETIC PRIVATE ACTIVE DRAFT', { exact: true })).toHaveCount(0)
})
test('clinical validation timeout reconciles without replaying POST', async ({ page }) => {
  const { controls, ext } = await setup(page)
  controls.fail = 503
  await page.getByRole('button', { name: 'Preparar validación', exact: true }).click()
  await page.getByRole('button', { name: 'Confirmar validación clínica', exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Servicio no disponible.' })).toBeVisible()
  ext.status = 'clinically_validated'
  await page.getByRole('button', { name: 'Comprobar conexión', exact: true }).click()
  await page
    .getByRole('button', { name: 'Consultar resultado de la operación', exact: true })
    .click()
  await expect(
    page.getByRole('alert').filter({ hasText: 'No se puede atribuir un resultado definitivo' }),
  ).toBeVisible()
  expect(controls.validation).toHaveLength(1)
})
test('clinical touch, keyboard, dark English and scaled reflow', async ({ browser }) => {
  const context = await browser.newContext({
    hasTouch: true,
    isMobile: true,
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
  })
  const page = await context.newPage()
  await setup(page)
  await page.getByRole('button', { name: 'Tema oscuro', exact: true }).tap()
  await page.getByLabel('Idioma', { exact: true }).selectOption('en')
  await expect(
    page.getByRole('heading', { name: 'Clinical review and validation', exact: true }),
  ).toBeVisible()
  await page.getByRole('textbox', { name: 'Validation clinical note', exact: true }).focus()
  await page.keyboard.type('SYNTHETIC ENGLISH NOTE')
  await page.setViewportSize({ width: 844, height: 390 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.setViewportSize({ width: 640, height: 450 })
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze()
    ).violations,
  ).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await context.close()
})
