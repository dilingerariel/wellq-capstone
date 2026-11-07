import { test, expect } from '@playwright/test'
import type { PortalSession } from '../src/types/session'
const fixture = JSON.parse(process.env.WELLQ_HTTP_FIXTURE || '{}') as {
  patient: string
  patientSession: PortalSession
  clinicianSession: PortalSession
  uploadSession: PortalSession
  pdfBytes: string
}
// No route interception. The backend verifies signed test claims and Mongo relationships.
test('patient reads FastAPI documents, both cursor pages, detail and catalog', async ({ page }) => {
  await page.addInitScript((session) => {
    window.wellqIdentity = { getSession: async () => session }
  }, fixture.patientSession)
  await page.goto('/exams')
  await expect(
    page.getByRole('link', { name: 'SYNTHETIC HTTP DOCUMENT 01', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('link', { name: /^SYNTHETIC HTTP DOCUMENT/ })).toHaveCount(6)
  await page.getByRole('button', { name: 'Página siguiente', exact: true }).click()
  await expect(
    page.getByRole('link', { name: 'SYNTHETIC HTTP DOCUMENT 07', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('link', { name: /^SYNTHETIC HTTP DOCUMENT/ })).toHaveCount(1)
  await page.getByRole('button', { name: 'Página anterior', exact: true }).click()
  await page.getByRole('link', { name: 'SYNTHETIC HTTP DOCUMENT 01', exact: true }).click()
  await expect(page.getByText('synthetic-http.pdf')).toBeVisible()
  await page.getByRole('link', { name: 'Catálogo de marcadores', exact: true }).click()
  await expect(page.getByText('cholesterol_total', { exact: true })).toBeVisible()
  await expect(page.getByText('Entorno de demostración', { exact: false })).toHaveCount(0)
})
test('real browser bytes reach signed test storage; FastAPI worker verifies a single upload', async ({
  page,
}) => {
  await page.addInitScript((session) => {
    window.wellqIdentity = { getSession: async () => session }
  }, fixture.uploadSession)
  await page.goto('/upload')
  await page.getByLabel('Seleccionar documento', { exact: true }).setInputFiles({
    name: 'synthetic-browser.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from(fixture.pdfBytes, 'base64'),
  })
  await page.getByLabel('Título del documento', { exact: true }).fill('SYNTHETIC BROWSER UPLOAD')
  await page.getByLabel('Fecha del examen', { exact: true }).fill('2026-01-01')
  await page.getByRole('checkbox').check()
  const transitions: string[] = []
  page.on('response', async (response) => {
    if (response.url().endsWith('/status') && response.status() === 200) {
      const body = await response.json()
      transitions.push(body.status)
    }
  })
  await page.getByRole('button', { name: 'Enviar documento', exact: true }).evaluate((button) => {
    ;(button as HTMLButtonElement).click()
    ;(button as HTMLButtonElement).click()
  })
  await expect(
    page.getByText(
      'Documento verificado y disponible. La revisión clínica es un paso independiente.',
      { exact: true },
    ),
  ).toBeVisible({ timeout: 45000 })
  await expect(
    page.getByText(
      'El servidor confirmó que puedes prescindir de la copia original para esta carga.',
      { exact: false },
    ),
  ).toBeVisible()
  expect(transitions).toContain('processing')
  expect(transitions).toContain('ready_for_review')
  const safe = await page.evaluate(
    () =>
      !JSON.stringify({ ...localStorage, ...sessionStorage }).includes('SYNTHETIC BROWSER UPLOAD'),
  )
  expect(safe).toBe(true)
  await page.getByRole('link', { name: 'Revisar extracción', exact: true }).click()
  await expect(page.getByLabel('Valor glucose', { exact: true })).toHaveValue('90')
  await page.getByLabel('Valor glucose', { exact: true }).fill('95')
  await page.getByLabel('Fecha de toma de muestra', { exact: true }).fill('2026-01-02')
  const identity = page.getByLabel('He comprobado que este documento me corresponde.', {
    exact: true,
  })
  if (await identity.isVisible()) await identity.check()
  const low = page.getByLabel('He revisado el marcador glucose marcado con baja confianza.', {
    exact: true,
  })
  if (await low.isVisible()) await low.check()
  await page.getByRole('button', { name: 'Revisar cambios', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Cambios que se enviarán' })).toBeVisible()
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
})
test('clinician reads authorized patient, server refuses unrelated patient', async ({ page }) => {
  await page.addInitScript((session) => {
    window.wellqIdentity = { getSession: async () => session }
  }, fixture.clinicianSession)
  await page.goto('/exams')
  await page.getByLabel('ID del paciente autorizado', { exact: true }).fill(fixture.patient)
  await page.getByRole('button', { name: 'Consultar paciente' }).click()
  await expect(
    page.getByRole('link', { name: 'SYNTHETIC HTTP DOCUMENT 01', exact: true }),
  ).toBeVisible()
  await page
    .getByLabel('ID del paciente autorizado', { exact: true })
    .fill('synthetic-unrelated-patient')
  const forbidden = page.waitForResponse(
    (response) =>
      response.url().includes('/patients/synthetic-unrelated-patient/') &&
      response.status() === 403,
  )
  await page.getByRole('button', { name: 'Consultar paciente' }).click()
  await forbidden
  await expect(page.getByRole('link', { name: /^SYNTHETIC HTTP DOCUMENT/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Cerrar sesión', exact: true })).toBeVisible()
})
