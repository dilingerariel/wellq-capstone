import { test, expect } from '@playwright/test'
import type { PortalSession } from '../src/types/session'
const fixture = JSON.parse(process.env.WELLQ_HTTP_FIXTURE || '{}') as {
  patient: string
  patientSession: PortalSession
  clinicianSession: PortalSession
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
