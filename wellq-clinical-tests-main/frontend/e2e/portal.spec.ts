import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { PortalSession } from '../src/types/session'

test('desktop navigation, details, cursor pagination, themes, i18n and accessibility', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Un espacio para una mejor atención' }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  await expect(page.getByText('Entorno de demostración', { exact: false })).toBeVisible()
  await page.screenshot({ path: 'test-results/overview-desktop.png', fullPage: true })
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([])
  await page.getByRole('link', { name: 'Ver todos los exámenes' }).click()
  await expect(page).toHaveURL(/\/exams$/)
  await page.getByRole('button', { name: 'Página siguiente' }).click()
  await expect(
    page.getByRole('link', { name: 'Documento anterior · DEMO', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Página anterior' }).click()
  await page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }).click()
  await expect(page.getByText('synthetic-document-01.pdf')).toBeVisible()
  await page.getByRole('link', { name: 'Volver a exámenes' }).click()
  await page.getByRole('button', { name: 'Tema oscuro' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([])
  await page.screenshot({ path: 'test-results/exams-dark.png', fullPage: true })
  await page.getByLabel('Idioma').selectOption('en')
  await expect(page.getByRole('heading', { name: 'Medical exams' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Medical exams' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(errors).toEqual([])
})

test('mobile keyboard navigation and patient role do not expose clinical views', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/exams')
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Saltar al contenido' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('main')).toBeFocused()
  await page.getByRole('button', { name: 'Abrir navegación' }).click()
  await page.getByRole('link', { name: 'Catálogo de marcadores' }).click()
  await expect(page.getByRole('heading', { name: 'Catálogo de marcadores' })).toBeVisible()
  await page.getByLabel('Vista de demostración').selectOption('patient')
  await page.goto('/clinical')
  // A full reload intentionally restores the default demonstration role.
  await page.getByLabel('Vista de demostración').selectOption('patient')
  await expect(page.getByRole('alert')).toContainText('Esta vista no está disponible para tu rol.')
  await page.getByRole('link', { name: 'Ir a mi espacio' }).click()
  await expect(page.getByRole('heading', { name: 'Tu información, en perspectiva' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: 'test-results/patient-mobile.png', fullPage: true })
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([])
})

test('tablet layout and frontend legacy bookmarks remain navigable', async ({ page }) => {
  await page.setViewportSize({ width: 820, height: 1180 })
  await page.goto('/dashboard/')
  await expect(
    page.getByRole('heading', { name: 'Un espacio para una mejor atención' }),
  ).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.goto('/demo')
  await expect(
    page.getByRole('heading', { name: 'Un espacio para una mejor atención' }),
  ).toBeVisible()
  await page.screenshot({ path: 'test-results/overview-tablet.png', fullPage: true })
})

test('API mode requires an external identity and never silently becomes a demo', async ({
  page,
}) => {
  await page.goto('http://127.0.0.1:5174/exams')
  await expect(
    page.getByRole('heading', { name: 'Conecta tu identidad para continuar' }),
  ).toBeVisible()
  await expect(page.getByText('API real', { exact: true })).toBeVisible()
  await expect(page.getByText('Entorno de demostración', { exact: false })).toHaveCount(0)
  await expect(page.getByLabel('Vista de demostración')).toHaveCount(0)
})

test('API clinician scope, forbidden response, no fake fallback and session invalidation', async ({
  page,
}) => {
  const requests: string[] = []
  await page.addInitScript(() => {
    const session: PortalSession = {
      accessToken: 'synthetic-external-test-token',
      tenantId: 'synthetic-tenant',
      resourceId: 'synthetic-clinician',
      role: 'clinician',
      permissions: ['clinical:read'],
      capabilities: [],
      expiresAt: Math.floor(Date.now() / 1000) + 300,
    }
    window.wellqIdentity = { getSession: async () => session }
  })
  let status = 403
  await page.route('**/api/v1/**', async (route) => {
    requests.push(route.request().url())
    expect(route.request().headers()['authorization']).toBe(
      ['Bearer', 'synthetic-external-test-token'].join(' '),
    )
    await route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: { code: 'FORBIDDEN', message: 'synthetic private body must not render' },
      }),
    })
  })
  await page.goto('http://127.0.0.1:5174/exams')
  await page.getByLabel('ID del paciente autorizado', { exact: true }).fill('synthetic-patient')
  await page.getByRole('button', { name: 'Consultar paciente' }).click()
  await expect(page.getByRole('alert')).toContainText('El servidor denegó el acceso')
  await expect(page.getByText('synthetic private body must not render')).toHaveCount(0)
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toHaveCount(0)
  expect(requests.every((url) => url.includes('/patients/synthetic-patient/clinical-tests'))).toBe(
    true,
  )
  status = 401
  await page.getByRole('button', { name: 'Volver a intentar' }).click()
  await expect(
    page.getByRole('heading', { name: 'Conecta tu identidad para continuar' }),
  ).toBeVisible()
  const count = requests.length
  await page.waitForTimeout(500)
  expect(requests.length).toBe(count)
})
