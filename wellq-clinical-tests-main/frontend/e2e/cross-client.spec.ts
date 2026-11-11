import { test, expect } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'

test('authorized clinician reviews the exact Flutter-created exam', async ({ page }) => {
  test.skip(
    process.env.WELLQ_CROSS_E2E !== '1',
    'Requires a new isolated stack and Flutter handoff',
  )
  const file = process.env.WELLQ_CROSS_MANIFEST
  const base = process.env.WELLQ_CROSS_WEB
  if (!file || !base) throw new Error('Missing isolated E2E manifest')
  const origin = new URL(base)
  if (origin.hostname !== '127.0.0.1' || origin.protocol !== 'http:')
    throw new Error('Only owned loopback portal permitted')
  const data = JSON.parse(readFileSync(file, 'utf8'))
  expect(data.synthetic_only).toBe(true)
  expect(data.patient_confirmed).toBe(true)
  expect(data.react_validated).toBeUndefined()
  expect(data.clinical_test_id).toMatch(/^ct_[a-f0-9]+$/)
  // No page.route/fulfill, fabricated session, or mocked API responses.
  const mutations: { path: string; body: Record<string, unknown>; status: number }[] = []
  page.on('response', (res) => {
    const req = res.request()
    if (req.method() === 'PATCH' || req.method() === 'POST') {
      const path = new URL(res.url()).pathname
      if (path.endsWith('/review') || path.endsWith('/extraction/validate'))
        mutations.push({ path, body: req.postDataJSON(), status: res.status() })
    }
  })
  await page.goto(base)
  await page.getByRole('button', { name: 'Profesional sintético', exact: true }).click()
  await page
    .getByRole('textbox', { name: 'ID del paciente autorizado', exact: true })
    .fill(data.patient)
  await page.getByRole('button', { name: 'Consultar paciente', exact: true }).click()
  // SPA navigation retains the authorized patient context, unlike a hard reload.
  await page.evaluate((id) => {
    history.pushState({}, '', `/exams/${encodeURIComponent(id)}/clinical-review`)
    dispatchEvent(new PopStateEvent('popstate'))
  }, data.clinical_test_id)
  await expect(page.getByRole('heading', { name: data.title, exact: true })).toBeVisible()
  await expect(
    page.getByRole('textbox', { name: 'Nota privada de revisión', exact: true }),
  ).toBeEnabled()
  await page
    .getByRole('textbox', { name: 'Nota privada de revisión', exact: true })
    .fill('SYNTHETIC CROSS PRIVATE REVIEW')
  await page.getByRole('button', { name: 'Preparar revisión', exact: true }).click()
  await page.getByRole('button', { name: 'Confirmar revisión del documento', exact: true }).click()
  await expect(page.getByText('El servidor registró la operación.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Consultar nuevamente', exact: true }).click()
  await expect(
    page.getByRole('textbox', { name: 'Nota privada de revisión', exact: true }),
  ).toBeDisabled()
  await page
    .getByRole('textbox', { name: 'Nota clínica de validación', exact: true })
    .fill('SYNTHETIC CROSS PRIVATE VALIDATION')
  await page.getByRole('button', { name: 'Preparar validación', exact: true }).click()
  await page.getByRole('button', { name: 'Confirmar validación clínica', exact: true }).click()
  await expect(page.getByText('Validado por un profesional', { exact: true })).toBeVisible()
  expect(mutations).toHaveLength(2)
  for (const mutation of mutations) {
    expect(mutation.path).toContain(`/clinical-tests/${data.clinical_test_id}/`)
    expect(mutation.status).toBe(200)
    expect(mutation.body.expected_version).toMatch(/^[a-f0-9]{64}$/)
  }
  const [review, validation] = mutations
  if (!review || !validation) throw new Error('Both clinical mutations must be observed')
  expect(review.body.expected_version).toBe(data.clinical_version)
  expect(validation.body.expected_version).not.toBe(review.body.expected_version)
  data.react_validated = true
  data.review_and_validation_requests = 2
  writeFileSync(file, JSON.stringify(data))
})
