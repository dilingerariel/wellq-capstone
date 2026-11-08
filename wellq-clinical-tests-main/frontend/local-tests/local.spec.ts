// No route interception, injected sessions, synthetic API fallback or browser signing.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
const runtime = new URL('../../backend/integration/.runtime/local-web/', import.meta.url)
const fixture = JSON.parse(readFileSync(new URL('fixture.json', runtime), 'utf8')) as {
  patient: string
}

test('manual local host supplies real patient/professional sessions and authorized responsive history', async ({
  page,
  context,
}) => {
  await page.goto('/exams')
  await expect(page.getByRole('complementary', { name: 'Entorno sintético local' })).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'SYNTHETIC LOCAL SAMPLE 1', exact: true }),
  ).toBeVisible()
  await page.goto('/history')
  await page.getByRole('button', { name: 'Profesional sintético', exact: true }).click()
  await page.getByLabel('ID del paciente autorizado', { exact: true }).fill(fixture.patient)
  await page.getByRole('button', { name: 'Consultar paciente', exact: true }).click()
  await expect(
    page.getByRole('table', { name: 'Mediciones recibidas de la API, en orden cronológico' }),
  ).toBeVisible()
  await expect(
    page.getByText(
      'El catálogo no está aprobado clínicamente. Se ocultan los puntajes numéricos.',
      { exact: true },
    ),
  ).toBeVisible()
  for (const width of [320, 360, 375, 390, 430, 768, 1024, 1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze()
    ).violations,
  ).toEqual([])
  await page.getByLabel('Idioma', { exact: true }).selectOption('en')
  await page.getByRole('button', { name: 'Dark theme', exact: true }).click()
  await page.setViewportSize({ width: 640, height: 420 })
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze()
    ).violations,
  ).toEqual([])
  await context.setOffline(true)
  await expect(page.getByRole('table')).toBeVisible()
  await context.setOffline(false)
  await page.getByRole('button', { name: 'Paciente sintético', exact: true }).click()
  await expect(page.getByRole('table')).toHaveCount(0)
})

test('browser upload, signed PUT, workers, confirmation and clinical validation use real API', async ({
  page,
}) => {
  const title = 'SYNTHETIC LOCAL BROWSER ' + Date.now()
  await page.goto('/upload')
  await page
    .getByLabel('Seleccionar documento', { exact: true })
    .setInputFiles(fileURLToPath(new URL('synthetic-example.pdf', runtime)))
  await page.getByLabel('Título del documento', { exact: true }).fill(title)
  await page
    .getByLabel('Fecha del examen', { exact: true })
    .fill(new Date().toISOString().slice(0, 10))
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Enviar documento', exact: true }).click()
  await expect(
    page.getByText(
      'Documento verificado y disponible. La revisión clínica es un paso independiente.',
      { exact: true },
    ),
  ).toBeVisible({ timeout: 45000 })
  await page.getByRole('link', { name: 'Revisar extracción', exact: true }).click()
  await expect(page.getByLabel('Valor glucose', { exact: true })).toHaveValue('90')
  const identity = page.getByLabel('He comprobado que este documento me corresponde.', {
    exact: true,
  })
  if (await identity.isVisible()) await identity.check()
  await page.getByRole('button', { name: 'Revisar cambios', exact: true }).click()
  await page.getByRole('button', { name: 'Confirmar datos revisados', exact: true }).click()
  await expect(
    page.getByText('Confirmación registrada por el servidor. No equivale a validación clínica.', {
      exact: true,
    }),
  ).toBeVisible()
  await page.goto('/exams')
  await page.getByRole('button', { name: 'Profesional sintético', exact: true }).click()
  await page.getByLabel('ID del paciente autorizado', { exact: true }).fill(fixture.patient)
  await page.getByRole('button', { name: 'Consultar paciente', exact: true }).click()
  await page.getByLabel('Estado del documento', { exact: true }).selectOption('ready_for_review')
  await page.getByRole('link', { name: title, exact: true }).click()
  await page.getByRole('link', { name: 'Revisión y validación clínica', exact: true }).click()
  await expect(page.getByLabel('Valor glucose', { exact: true })).toHaveValue('90')
  await page
    .getByLabel('Nota privada de revisión', { exact: true })
    .fill('SYNTHETIC LOCAL PRIVATE NOTE')
  await page.getByRole('button', { name: 'Preparar revisión', exact: true }).click()
  await page.getByRole('button', { name: 'Confirmar revisión del documento', exact: true }).click()
  await expect(page.getByText('El servidor registró la operación.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Consultar nuevamente', exact: true }).click()
  await page.getByRole('button', { name: 'Preparar validación', exact: true }).click()
  await page.getByRole('button', { name: 'Confirmar validación clínica', exact: true }).click()
  await expect(page.getByText('Validado por un profesional', { exact: true })).toBeVisible()
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }).includes(
        'SYNTHETIC LOCAL PRIVATE NOTE',
      ),
    ),
  ).toBe(false)
})

test('loopback bridge rejects cross-origin authority requests and missing local nonce', async ({
  request,
}) => {
  const privateKey = fileURLToPath(new URL('../private.pem', runtime)).replaceAll('\\', '/')
  const deniedFile = await request.get('/@fs/' + privateKey)
  expect([403, 404]).toContain(deniedFile.status())
  expect(await deniedFile.text()).not.toMatch(/BEGIN (?:RSA )?PRIVATE KEY/)
  expect(
    (
      await request.get('/__wellq_local/adapter.js', {
        headers: { Origin: 'https://untrusted.invalid' },
      })
    ).status(),
  ).toBe(403)
  expect(
    (await request.post('/__wellq_local/session', { data: { role: 'clinician' } })).status(),
  ).toBe(403)
  expect((await request.post('/__wellq_local/stop')).status()).toBe(403)
})
