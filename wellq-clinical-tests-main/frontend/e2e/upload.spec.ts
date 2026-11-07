import { test, expect } from './fixtures'
import type { Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

async function patient(page: Page) {
  await page.addInitScript(() => {
    let changed = false
    window.wellqIdentity = {
      getSession: async () => ({
        accessToken: 'synthetic-upload-session',
        role: 'patient',
        tenantId: 'synthetic-tenant',
        resourceId: changed ? 'synthetic-next-patient' : 'synthetic-patient',
        permissions: ['clinical:read', 'clinical:write'],
        capabilities: [],
        expiresAt: Math.floor(Date.now() / 1000) + 900,
      }),
      refreshSession: async () => window.wellqIdentity!.getSession(),
      subscribe: (callback) => {
        const notify = () => {
          changed = true
          callback()
        }
        window.addEventListener('synthetic-upload-account-change', notify)
        return () => window.removeEventListener('synthetic-upload-account-change', notify)
      },
    }
  })
}
async function fill(page: Page) {
  await page.goto('http://127.0.0.1:5174/upload')
  await page.getByLabel('Seleccionar documento', { exact: true }).setInputFiles({
    name: 'synthetic.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-synthetic-browser-interception-only'),
  })
  await page.getByLabel('Título del documento', { exact: true }).fill('Synthetic upload')
  await page.getByLabel('Fecha del examen', { exact: true }).fill('2026-01-01')
}
type Options = {
  initiateRefusal?: boolean
  putFailure?: boolean
  completeFailure?: boolean
  processing?: boolean
  expired?: boolean
  delayPut?: boolean
}
async function mockApi(page: Page, options: Options = {}) {
  const seen = {
    initiate: 0,
    put: 0,
    complete: 0,
    refresh: 0,
    keys: [] as string[],
    storageAuthorization: false,
  }
  const descriptor = () => ({
    method: 'PUT',
    signed_url: 'http://127.0.0.1:5199/synthetic-storage',
    required_headers: { 'Content-Type': 'application/pdf', 'x-goog-if-generation-match': '0' },
    expires_at: new Date(Date.now() + (options.expired ? -1000 : 900000)).toISOString(),
  })
  let confirmed = false
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    let status = 200,
      body: unknown
    if (path.endsWith('/initiate')) {
      status = options.initiateRefusal ? 422 : 201
      seen.initiate++
      seen.keys.push(route.request().headers()['idempotency-key'] || '')
      body = {
        clinical_test_id: 'synthetic-uploaded',
        upload_id: 'synthetic-u',
        status: 'initiated',
        upload: descriptor(),
      }
    } else if (path.endsWith('/refresh-url')) {
      seen.refresh++
      options.expired = false
      body = { upload_id: 'synthetic-u', status: 'initiated', upload: descriptor() }
    } else if (path.endsWith('/complete')) {
      seen.complete++
      seen.keys.push(route.request().headers()['idempotency-key'] || '')
      status = options.completeFailure ? 503 : 200
      confirmed = !options.completeFailure
      body = {
        clinical_test_id: 'synthetic-uploaded',
        upload_id: 'synthetic-u',
        status: 'processing',
        local_file_can_be_deleted: false,
        status_url: '/api/v1/clinical-tests/uploads/synthetic-u/status',
      }
    } else if (path.endsWith('/status'))
      body = {
        clinical_test_id: 'synthetic-uploaded',
        upload_id: 'synthetic-u',
        status: !confirmed ? 'initiated' : options.processing ? 'processing' : 'ready_for_review',
        processing: {
          malware_scan: confirmed && !options.processing ? 'passed' : 'pending',
          mime_validation: confirmed && !options.processing ? 'passed' : 'pending',
        },
        local_file_can_be_deleted: confirmed && !options.processing,
      }
    else body = { items: [], next_cursor: null }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.route('http://127.0.0.1:5199/**', async (route) => {
    if (route.request().method() === 'OPTIONS') {
      await route.fulfill({
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'PUT',
          'Access-Control-Allow-Headers': 'Content-Type,x-goog-if-generation-match',
        },
      })
      return
    }
    seen.put++
    seen.storageAuthorization = !!route.request().headers()['authorization']
    if (options.delayPut) await new Promise((resolve) => setTimeout(resolve, 5000))
    try {
      await route.fulfill({
        status: options.putFailure ? 403 : 200,
        headers: { 'Access-Control-Allow-Origin': '*' },
        body: '',
      })
    } catch {
      /* The browser may already have cancelled the synthetic request. */
    }
  })
  return seen
}
test('upload retries failed PUT with refreshed authorization, stable identity and no backend bearer in storage', async ({
  page,
}) => {
  await patient(page)
  const options = { putFailure: true }
  const seen = await mockApi(page, options)
  await fill(page)
  await page.getByRole('button', { name: 'Enviar documento', exact: true }).click()
  await expect(
    page.getByText('No se confirmó la transferencia al almacenamiento.', { exact: false }),
  ).toBeVisible()
  expect(seen.complete).toBe(0)
  options.putFailure = false
  await page.getByRole('button', { name: 'Continuar o reintentar', exact: true }).click()
  await expect(page.getByText('Documento verificado y disponible.', { exact: false })).toBeVisible()
  expect(seen).toMatchObject({
    initiate: 1,
    put: 2,
    complete: 1,
    refresh: 1,
    storageAuthorization: false,
  })
})
test('a definitive first validation refusal allows correction without losing the selected File', async ({
  page,
}) => {
  await patient(page)
  const options = { initiateRefusal: true }
  const seen = await mockApi(page, options)
  await fill(page)
  await page.getByRole('button', { name: 'Enviar documento', exact: true }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByLabel('Título del documento', { exact: true })).toBeEnabled()
  await expect(page.getByText('synthetic.pdf', { exact: true })).toBeVisible()
  expect(seen.put).toBe(0)
  options.initiateRefusal = false
  await page
    .getByLabel('Título del documento', { exact: true })
    .fill('Corrected synthetic metadata')
  await page.getByRole('button', { name: 'Enviar documento', exact: true }).click()
  await expect(page.getByText('Documento verificado y disponible.', { exact: false })).toBeVisible()
  expect(seen).toMatchObject({ initiate: 2, put: 1, complete: 1 })
  expect(seen.keys[0]).not.toBe(seen.keys[1])
})
test('expired authorization is refreshed before bytes, double click does not duplicate, complete failure retains the original', async ({
  page,
}) => {
  await patient(page)
  const options = { expired: true, completeFailure: true }
  const seen = await mockApi(page, options)
  await fill(page)
  await page.getByRole('button', { name: 'Enviar documento', exact: true }).evaluate((button) => {
    ;(button as HTMLButtonElement).click()
    ;(button as HTMLButtonElement).click()
  })
  await expect(
    page
      .getByText('Un servicio necesario no está disponible. Inténtalo más tarde.', { exact: true })
      .first(),
  ).toBeVisible()
  expect(seen).toMatchObject({ initiate: 1, refresh: 1, put: 1, complete: 1 })
  await expect(page.getByText('synthetic.pdf', { exact: true })).toBeVisible()
  options.completeFailure = false
  await page.getByRole('button', { name: 'Comprobar conexión', exact: true }).click()
  await page.getByRole('button', { name: 'Continuar o reintentar', exact: true }).click()
  await expect(page.getByText('Documento verificado y disponible.', { exact: false })).toBeVisible()
  expect(seen.put).toBe(1)
  expect(seen.keys[1]).toBe(seen.keys[2])
})
test('offline interruption retains file and metadata, reconnect never automatically replays a write', async ({
  page,
  context,
}) => {
  await patient(page)
  const options = { delayPut: true }
  const seen = await mockApi(page, options)
  await fill(page)
  await page.getByRole('button', { name: 'Enviar documento', exact: true }).click()
  await expect.poll(() => seen.put).toBe(1)
  await context.setOffline(true)
  await expect(page.getByText('Operación interrumpida.', { exact: false })).toBeVisible()
  await expect(page.getByText('synthetic.pdf', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Título del documento', { exact: true })).toHaveValue(
    'Synthetic upload',
  )
  options.delayPut = false
  await context.setOffline(false)
  await expect(
    page.getByRole('button', { name: 'Continuar o reintentar', exact: true }),
  ).toBeEnabled()
  expect(seen.complete).toBe(0)
  expect(seen.put).toBe(1)
  await page.getByRole('button', { name: 'Continuar o reintentar', exact: true }).click()
  await expect(page.getByText('Documento verificado y disponible.', { exact: false })).toBeVisible()
  expect(seen.initiate).toBe(1)
})
test('cancel and account switch reject late responses and clear the file across the identity boundary', async ({
  page,
}) => {
  await patient(page)
  const seen = await mockApi(page, { delayPut: true })
  await fill(page)
  await page.getByRole('button', { name: 'Enviar documento', exact: true }).click()
  await expect.poll(() => seen.put).toBe(1)
  await page.getByRole('button', { name: 'Cancelar operación', exact: true }).click()
  await expect(page.getByText('Operación local cancelada.', { exact: false })).toBeVisible()
  expect(seen.complete).toBe(0)
  await page.evaluate(() => window.dispatchEvent(new Event('synthetic-upload-account-change')))
  await expect(page.getByText('synthetic.pdf', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Título del documento', { exact: true })).toHaveValue('')
  await expect(page.getByRole('button', { name: 'Enviar documento', exact: true })).toBeDisabled()
})
test('file validation, dark theme, English, keyboard and RAM continuity across portal navigation', async ({
  page,
}) => {
  await patient(page)
  await mockApi(page)
  await fill(page)
  await page.getByRole('link', { name: 'Exámenes', exact: true }).click()
  await page.getByRole('link', { name: 'Volver a la carga', exact: true }).click()
  await expect(page.getByText('synthetic.pdf', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Título del documento', { exact: true })).toHaveValue(
    'Synthetic upload',
  )
  await page.getByLabel('Seleccionar documento', { exact: true }).setInputFiles({
    name: 'synthetic-large.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.alloc(20 * 1024 * 1024 + 1),
  })
  await expect(page.getByRole('alert')).toContainText('hasta 20 MiB')
  await expect(page.getByRole('button', { name: 'Enviar documento', exact: true })).toBeDisabled()
  await page.getByLabel('Seleccionar documento', { exact: true }).setInputFiles({
    name: 'synthetic.exe.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('invalid'),
  })
  await expect(page.getByRole('alert')).toContainText('extensión y el tipo')
  await page.getByRole('button', { name: 'Tema oscuro', exact: true }).click()
  await page.getByLabel('Idioma', { exact: true }).selectOption('en')
  await expect(page.getByRole('heading', { name: 'Upload exam', exact: true })).toBeVisible()
  await page.getByLabel('Document title', { exact: true }).focus()
  await page.keyboard.type('Keyboard draft')
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze()
    ).violations,
  ).toEqual([])
})
