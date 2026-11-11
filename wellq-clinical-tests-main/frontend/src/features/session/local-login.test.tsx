import { readFileSync } from 'node:fs'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { localIdentity } from '../../../scripts/local-identity.mjs'
import { App } from '../../app/App'
import { RuntimeProvider } from '../../app/runtime'
import es from '../../i18n/es.json'

vi.hoisted(() => {
  vi.stubEnv('VITE_DATA_MODE', 'api')
})

const script = readFileSync('scripts/local_adapter.js', 'utf8')
  .replace('__LOCAL_NONCE__', 'synthetic-unit-nonce')
  .replace('__LOCAL_PATIENT__', 'synthetic-local-patient-unit')
let requestedRoles: string[]
let expired = false
function install(professional = true) {
  const element = document.createElement('script')
  element.dataset.wellqEntry = professional ? 'clinician' : 'legacy'
  Object.defineProperty(document, 'currentScript', { configurable: true, value: element })
  window.eval(script)
  Object.defineProperty(document, 'currentScript', { configurable: true, value: null })
  window.dispatchEvent(new Event('DOMContentLoaded'))
}
beforeEach(() => {
  requestedRoles = []
  expired = false
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string | URL, options?: RequestInit) => {
      const path = new URL(String(url), 'http://localhost').pathname
      if (path === '/health') return new Response('{"status":"ok"}', { status: 200 })
      if (path !== '/__wellq_local/session')
        throw new Error('Unexpected HTTP in isolated login test')
      expect(options?.method).toBe('POST')
      expect(options?.credentials).toBe('omit')
      expect(options?.redirect).toBe('error')
      expect(options?.headers).toHaveProperty('X-WellQ-Local', 'synthetic-unit-nonce')
      const { role } = JSON.parse(options?.body as string)
      requestedRoles.push(role)
      // Explicit HTTP double, not a signed JWT and never sent to a backend.
      return new Response(
        JSON.stringify({
          accessToken: 'synthetic-ui-unit-only',
          role,
          tenantId: 'synthetic-local-unit',
          resourceId: `synthetic-local-${role}-unit`,
          permissions: ['clinical:read', 'clinical:review', 'extractions:validate'],
          capabilities: [],
          expiresAt: Math.floor(Date.now() / 1000) + (expired ? -10 : 300),
        }),
        { status: 200 },
      )
    }),
  )
})
afterEach(() => {
  delete window.wellqIdentity
  document
    .querySelectorAll('aside[aria-label="Entorno sintético local"]')
    .forEach((panel) => panel.remove())
  vi.unstubAllGlobals()
})
function portal() {
  return render(
    <RuntimeProvider>
      <MemoryRouter initialEntries={['/clinical']}>
        <App />
      </MemoryRouter>
    </RuntimeProvider>,
  )
}

it('enters the clinician portal through the real gate, renews and logs out without automatic re-entry', async () => {
  install()
  expect(await window.wellqIdentity!.getSession()).toBeNull()
  portal()
  const user = userEvent.setup()
  expect(await screen.findByRole('heading', { name: es.accessProfessional })).toBeInTheDocument()
  const enter = screen.getByRole('button', { name: es.signIn })
  await waitFor(() => expect(enter).toBeEnabled())
  expect(requestedRoles).toEqual([])
  expect(screen.queryByLabelText(es.authorizedPatient)).not.toBeInTheDocument()
  await user.click(enter)
  expect(
    await screen.findByRole('heading', { name: es.clinicalTitle }, { timeout: 5000 }),
  ).toBeInTheDocument()
  expect(requestedRoles).toEqual(['clinician'])
  const navigation = screen.getByRole('navigation', { name: es.workspace })
  expect(within(navigation).getByRole('link', { name: es.recordsReportsNav })).toBeInTheDocument()
  expect(within(navigation).queryByRole('link', { name: es.uploadTitle })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Paciente sintético' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: es.renewSession }))
  await waitFor(() => expect(requestedRoles).toEqual(['clinician', 'clinician']))
  await user.click(screen.getByRole('button', { name: es.signOut }))
  expect(await screen.findByRole('heading', { name: es.accessProfessional })).toBeInTheDocument()
  expect(screen.queryByLabelText(es.authorizedPatient)).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: es.reloadIdentity }))
  expect(await window.wellqIdentity!.getSession()).toBeNull()
  expect(requestedRoles).toHaveLength(2)
}, 15000)

it('keeps protected content closed when the synthetic host returns an expired session', async () => {
  expired = true
  install()
  portal()
  const enter = await screen.findByRole('button', { name: es.signIn })
  await waitFor(() => expect(enter).toBeEnabled())
  await userEvent.setup().click(enter)
  await waitFor(() =>
    expect(screen.getByRole('region', { name: es.accessProfessional })).toHaveTextContent(
      es.session_expired,
    ),
  )
  expect(screen.getByRole('heading', { name: es.accessProfessional })).toBeInTheDocument()
  expect(screen.queryByLabelText(es.authorizedPatient)).not.toBeInTheDocument()
})

it('preserves the legacy patient adapter for existing isolated integration tools', async () => {
  install(false)
  await window.wellqIdentity!.getSession()
  expect(requestedRoles).toEqual(['patient'])
  await window.wellqIdentity!.signOut!()
  expect(await window.wellqIdentity!.getSession()).toBeNull()
})

it('does not inject the local adapter in production builds and refuses production dev-server use', () => {
  expect(() =>
    localIdentity({ professionalLogin: true, apiTarget: 'https://identity.example.org' }),
  ).toThrow('loopback bridge')
  const plugin = localIdentity({ professionalLogin: true })
  expect(plugin.apply).toBe('serve')
  expect(() => plugin.configResolved({ isProduction: true })).toThrow('development server')
  plugin.configResolved({ isProduction: false })
  expect(plugin.transformIndexHtml()[0]?.attrs?.['data-wellq-entry']).toBe('clinician')
})
