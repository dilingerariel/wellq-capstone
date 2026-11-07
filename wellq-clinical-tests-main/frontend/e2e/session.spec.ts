import { test, expect } from './fixtures'
import { demoSource } from '../src/features/demo/source'

test('API patient reads server data and clears the previous identity cache on session changes', async ({
  page,
}) => {
  await page.addInitScript(() => {
    let changed = false
    window.wellqIdentity = {
      getSession: async () => ({
        accessToken: changed ? 'synthetic-next-token' : 'synthetic-first-token',
        tenantId: 'synthetic-tenant',
        resourceId: changed ? 'synthetic-other-patient' : 'demo-patient',
        role: 'patient',
        permissions: ['clinical:read'],
        capabilities: [],
        expiresAt: Math.floor(Date.now() / 1000) + 300,
      }),
      subscribe: (callback) => {
        const notify = () => {
          changed = true
          callback()
        }
        window.addEventListener('synthetic-session-change', notify)
        return () => window.removeEventListener('synthetic-session-change', notify)
      },
    }
  })
  const syntheticPage = await demoSource.list({}, 'demo-patient')
  const paths: string[] = []
  await page.route('**/api/v1/**', async (route) => {
    paths.push(new URL(route.request().url()).pathname)
    const changed =
      route.request().headers()['authorization'] === ['Bearer', 'synthetic-next-token'].join(' ')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(changed ? { items: [], next_cursor: null } : syntheticPage),
    })
  })
  await page.goto('http://127.0.0.1:5174/exams')
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  await expect(page.getByLabel('ID del paciente autorizado')).toHaveCount(0)
  await expect(page.getByText('Entorno de demostración', { exact: false })).toHaveCount(0)
  await page.evaluate(() => window.dispatchEvent(new Event('synthetic-session-change')))
  await expect(page.getByRole('heading', { name: 'Todavía no hay documentos' })).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toHaveCount(0)
  expect(paths.every((path) => path === '/api/v1/clinical-tests')).toBe(true)
})

test('changing the clinical patient clears the previous document and does not relabel its details', async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.wellqIdentity = {
      getSession: async () => ({
        accessToken: 'synthetic-clinical-context-token',
        role: 'clinician',
        tenantId: 'synthetic-tenant',
        resourceId: 'synthetic-clinician',
        permissions: ['clinical:read'],
        capabilities: [],
        expiresAt: Math.floor(Date.now() / 1000) + 300,
      }),
    }
  })
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const body = path.includes('/patients/synthetic-second-patient/')
      ? { items: [], next_cursor: null }
      : path.includes('/patients/')
        ? await demoSource.list({}, 'demo-patient')
        : await demoSource.detail('demo-exam-01')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })
  })
  await page.goto('http://127.0.0.1:5174/exams')
  await page.getByLabel('ID del paciente autorizado', { exact: true }).fill('demo-patient')
  await page.getByRole('button', { name: 'Consultar paciente' }).click()
  await page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }).click()
  await expect(page.getByText('synthetic-document-01.pdf')).toBeVisible()
  await page
    .getByLabel('ID del paciente autorizado', { exact: true })
    .fill('synthetic-second-patient')
  await page.getByRole('button', { name: 'Consultar paciente' }).click()
  await expect(page).toHaveURL(/\/exams$/)
  await expect(page.getByRole('heading', { name: 'Todavía no hay documentos' })).toBeVisible()
  await expect(page.getByText('synthetic-document-01.pdf')).toHaveCount(0)
})
