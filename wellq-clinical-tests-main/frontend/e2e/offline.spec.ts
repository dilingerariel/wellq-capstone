import { test, expect } from './fixtures'
import { demoSource } from '../src/features/demo/source'

test('identity network failure preserves the draft and cached view, gates reads until explicit revalidation', async ({
  page,
  context,
}) => {
  await page.addInitScript(() => {
    let unavailable = false
    window.addEventListener('synthetic-identity-outage', () => {
      unavailable = true
    })
    window.addEventListener('synthetic-identity-restored', () => {
      unavailable = false
    })
    const session = {
      accessToken: 'synthetic-offline-identity',
      role: 'clinician',
      tenantId: 'synthetic-tenant',
      resourceId: 'synthetic-clinician',
      permissions: ['clinical:read'],
      capabilities: [],
      expiresAt: Math.floor(Date.now() / 1000) + 300,
    }
    window.wellqIdentity = {
      getSession: async () => session,
      refreshSession: async () => {
        if (unavailable) throw new TypeError('Synthetic provider network failure')
        return session
      },
    }
  })
  let disconnected = false,
    reads = 0
  const data = await demoSource.list({}, 'demo-patient')
  await page.route('**/health', (route) =>
    disconnected
      ? route.abort('internetdisconnected')
      : route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' }),
  )
  await page.route('**/api/v1/**', async (route) => {
    reads++
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(data),
    })
  })
  await page.goto('http://127.0.0.1:5174/exams')
  await page.getByLabel('ID del paciente autorizado', { exact: true }).fill('demo-patient')
  await page.getByRole('button', { name: 'Consultar paciente' }).click()
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  await page
    .getByLabel('ID del paciente autorizado', { exact: true })
    .fill('synthetic-private-draft')
  await page.evaluate(() => window.dispatchEvent(new Event('synthetic-identity-outage')))
  disconnected = true
  await context.setOffline(true)
  await expect(page.getByRole('button', { name: 'Consultar paciente' })).toBeDisabled()
  const before = reads
  disconnected = false
  await context.setOffline(false)
  await expect(
    page.getByText(
      'Identidad temporalmente sin verificar; se conservan los datos de esta sesión en memoria',
      { exact: true },
    ),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Consultar paciente' })).toBeDisabled()
  await expect(page.getByLabel('ID del paciente autorizado', { exact: true })).toHaveValue(
    'synthetic-private-draft',
  )
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  expect(reads).toBe(before)
  await page.evaluate(() => window.dispatchEvent(new Event('synthetic-identity-restored')))
  await page.getByRole('button', { name: 'Renovar sesión', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Consultar paciente' })).toBeEnabled()
  await expect.poll(() => reads).toBe(before + 1)
  await expect(page.getByLabel('ID del paciente autorizado', { exact: true })).toHaveValue(
    'synthetic-private-draft',
  )
})

test('offline preserves cached reads and unsent form, reconnect revalidates once, service failure is not fake success', async ({
  page,
  context,
}) => {
  await page.addInitScript(() => {
    const session = {
      accessToken: 'synthetic-provider-token',
      role: 'clinician',
      tenantId: 'synthetic-tenant',
      resourceId: 'synthetic-clinician',
      permissions: ['clinical:read'],
      capabilities: [],
      expiresAt: Math.floor(Date.now() / 1000) + 300,
    }
    window.wellqIdentity = {
      getSession: async () => session,
      refreshSession: async () => {
        window.dispatchEvent(new Event('synthetic-renew'))
        return session
      },
    }
  })
  const data = await demoSource.list({}, 'demo-patient')
  let reads = 0
  let failure = false
  let renewals = 0
  let disconnected = false
  await page.route('**/health', (route) =>
    disconnected
      ? route.abort('internetdisconnected')
      : route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' }),
  )
  await page.exposeFunction('recordSyntheticRenew', () => {
    renewals++
  })
  await page.addInitScript(() =>
    window.addEventListener('synthetic-renew', () => {
      void (
        window as unknown as { recordSyntheticRenew: () => Promise<void> }
      ).recordSyntheticRenew()
    }),
  )
  await page.route('**/api/v1/**', async (route) => {
    if (disconnected) {
      await route.abort('internetdisconnected')
      return
    }
    const catalog = new URL(route.request().url()).pathname.endsWith('/marker-catalog')
    if (!catalog) reads++
    await route.fulfill({
      status: failure ? 503 : 200,
      contentType: 'application/json',
      body: JSON.stringify(
        failure ? { detail: { code: 'UNAVAILABLE' } } : catalog ? await demoSource.catalog() : data,
      ),
    })
  })
  await page.goto('http://127.0.0.1:5174/exams')
  await page.getByLabel('ID del paciente autorizado', { exact: true }).fill('demo-patient')
  await page.getByRole('button', { name: 'Consultar paciente' }).click()
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  // Load the public route module before testing RAM-only continuity in development.
  await page.getByRole('link', { name: 'Catálogo de marcadores', exact: true }).click()
  await expect(page.getByText('DEMO_MARKER', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Exámenes', exact: true }).click()
  await page
    .getByLabel('ID del paciente autorizado', { exact: true })
    .fill('synthetic-unsent-draft')
  disconnected = true
  await context.setOffline(true)
  await expect(page.getByText('Sin conexión de red', { exact: true }).first()).toBeVisible()
  await expect(page.getByLabel('ID del paciente autorizado', { exact: true })).toHaveValue(
    'synthetic-unsent-draft',
  )
  await expect(page.getByRole('button', { name: 'Consultar paciente' })).toBeDisabled()
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'Catálogo de marcadores', exact: true }).click()
  await expect(page.getByText('DEMO_MARKER', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Exámenes', exact: true }).click()
  const previousReads = reads
  disconnected = false
  await context.setOffline(false)
  await expect(page.getByText('API accesible', { exact: true })).toBeVisible()
  await expect.poll(() => renewals).toBe(1)
  await expect.poll(() => reads).toBe(previousReads + 1)
  await expect(page.getByLabel('ID del paciente autorizado', { exact: true })).toHaveValue(
    'synthetic-unsent-draft',
  )
  failure = true
  await page.getByRole('button', { name: 'Actualizar', exact: true }).click()
  await expect(
    page.getByText('Servicio temporalmente no disponible', { exact: true }).first(),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  await expect(page.getByText('Entorno de demostración', { exact: false })).toHaveCount(0)
})

test('production PWA reopens offline and only caches public static shell resources', async ({
  page,
  context,
}) => {
  await page.goto('http://127.0.0.1:4173/exams')
  await expect(page.getByRole('heading', { name: 'Exámenes médicos' })).toBeVisible()
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
    if (!navigator.serviceWorker.controller)
      await new Promise<void>((resolve) =>
        navigator.serviceWorker.addEventListener('controllerchange', () => resolve(), {
          once: true,
        }),
      )
  })
  await page.route('**/api/v1/private-probe', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"sentinel":"synthetic-clinical-content-never-cache"}',
    }),
  )
  await page.evaluate(async () => {
    await fetch('/api/v1/private-probe', {
      headers: { Authorization: ['Bearer', 'synthetic-private-test-token'].join(' ') },
      cache: 'no-store',
    })
  })
  const cached = await page.evaluate(async () => {
    const result: string[] = []
    for (const name of await caches.keys())
      for (const request of await (await caches.open(name)).keys())
        result.push(new URL(request.url).pathname)
    return result
  })
  expect(cached).toContain('/index.html')
  expect(
    cached.every(
      (path) =>
        path === '/index.html' ||
        path === '/manifest.webmanifest' ||
        path === '/wellq.svg' ||
        /^\/(assets|icons)\//.test(path),
    ),
  ).toBe(true)
  expect(cached.some((path) => /api|patient|clinical|exams/.test(path))).toBe(false)
  await context.setOffline(true)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Exámenes médicos' })).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'Catálogo de marcadores', exact: true }).click()
  await expect(page.getByText('DEMO_MARKER', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/pwa-offline.png', fullPage: true })
})

test('authorized sign-in/out uses provider methods and clears all prior private views', async ({
  page,
}) => {
  await page.addInitScript(() => {
    let active = false
    window.wellqIdentity = {
      getSession: async () =>
        active
          ? {
              accessToken: 'synthetic-login-token',
              role: 'patient',
              tenantId: 'synthetic-tenant',
              resourceId: 'demo-patient',
              permissions: ['clinical:read'],
              capabilities: [],
              expiresAt: Math.floor(Date.now() / 1000) + 300,
            }
          : null,
      signIn: async () => {
        active = true
      },
      signOut: async () => {
        active = false
      },
    }
  })
  await page.route('**/api/v1/**', async (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(await demoSource.list({}, 'demo-patient')),
    }),
  )
  await page.goto('http://127.0.0.1:5174/exams')
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Conecta tu identidad para continuar' }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Panel de laboratorio · DEMO', exact: true }),
  ).toHaveCount(0)
  const persistent = await page.evaluate(() => ({
    storage: JSON.stringify(localStorage),
    session: JSON.stringify(sessionStorage),
  }))
  expect(JSON.stringify(persistent)).not.toContain('synthetic-login-token')
})
