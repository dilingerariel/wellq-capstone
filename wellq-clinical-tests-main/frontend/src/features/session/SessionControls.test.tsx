import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useRuntime } from '../../app/runtime'
import i18n from '../../i18n'
import es from '../../i18n/es.json'
import en from '../../i18n/en.json'
import { SessionControls, SessionGate } from './SessionControls'

vi.mock('../../app/runtime', () => ({ useRuntime: vi.fn() }))
type Runtime = ReturnType<typeof useRuntime>
let state: Partial<Runtime>
function gate(path = '/clinical') {
  vi.mocked(useRuntime).mockReturnValue(state as Runtime)
  return render(
    <MemoryRouter initialEntries={[path]}>
      <SessionGate />
    </MemoryRouter>,
  )
}
beforeEach(async () => {
  await i18n.changeLanguage('es')
  state = {
    mode: 'api',
    session: null,
    sessionPhase: 'signed-out',
    loading: false,
    connection: 'online',
    canSignIn: true,
    canRenew: true,
    signIn: vi.fn(),
    reloadIdentity: vi.fn(),
    signOut: vi.fn(),
  }
})

describe('delegated access presentation', () => {
  it.each([
    ['es', es],
    ['en', en],
  ] as const)('localizes the card and delegates keyboard sign-in (%s)', async (language, text) => {
    await i18n.changeLanguage(language)
    gate()
    expect(screen.getByRole('heading', { name: text.accessProfessional })).toBeInTheDocument()
    expect(screen.getByText(text.accessDelegatedHelp)).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    const user = userEvent.setup()
    await user.tab()
    expect(screen.getByRole('button', { name: text.signIn })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(state.signIn).toHaveBeenCalledOnce()
    expect(state.reloadIdentity).not.toHaveBeenCalled()
  })
  it('does not offer a fabricated login when the provider has no sign-in capability', () => {
    state.canSignIn = false
    state.sessionPhase = 'unavailable'
    gate()
    expect(screen.queryByRole('button', { name: es.signIn })).not.toBeInTheDocument()
    expect(screen.getByText(es.accessProviderHelp)).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(es.session_unavailable)
  })
  it('announces verification and blocks duplicate actions while loading', () => {
    state.loading = true
    state.sessionPhase = 'loading'
    gate()
    expect(screen.getByRole('region')).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toHaveTextContent(es.session_loading)
    for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
  })
  it('blocks actions offline and explains the connection requirement', () => {
    state.connection = 'offline'
    gate()
    expect(screen.getByText(es.accessOffline)).toBeInTheDocument()
    for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
  })
  it('announces an error and preserves the explicit verification action', async () => {
    state.sessionPhase = 'error'
    gate()
    expect(screen.getByRole('alert')).toHaveTextContent(es.session_error)
    await userEvent.setup().click(screen.getByRole('button', { name: es.reloadIdentity }))
    expect(state.reloadIdentity).toHaveBeenCalledOnce()
  })
  it('retains the expired-session message without exposing clinical data', () => {
    state.sessionPhase = 'expired'
    gate()
    expect(screen.getByRole('status')).toHaveTextContent(es.session_expired)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
  it.each(['/patient', '/upload', '/exams/synthetic/extraction'])(
    'keeps patient entry distinct on %s',
    (path) => {
      gate(path)
      expect(screen.getByRole('heading', { name: es.accessPatient })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: es.signIn })).toBeInTheDocument()
      expect(screen.queryByText(es.accessProfessional)).not.toBeInTheDocument()
    },
  )
  it('keeps existing renewal and logout controls wired to the runtime', async () => {
    state.session = {} as NonNullable<Runtime['session']>
    state.sessionPhase = 'authenticated'
    vi.mocked(useRuntime).mockReturnValue(state as Runtime)
    render(<SessionControls />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: es.renewSession }))
    await user.click(screen.getByRole('button', { name: es.signOut }))
    expect(state.reloadIdentity).toHaveBeenCalledOnce()
    expect(state.signOut).toHaveBeenCalledOnce()
  })
  it('keeps dictionary keys aligned', () => {
    expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort())
  })
})
