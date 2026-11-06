import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { App } from './App'
import { RuntimeProvider } from './runtime'
import es from '../i18n/es.json'
import en from '../i18n/en.json'
function portal(path = '/exams') {
  return render(
    <RuntimeProvider>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </RuntimeProvider>,
  )
}
describe('portal navigation and states', () => {
  it('has matching Spanish and English dictionaries', () =>
    expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort()))
  it('lists synthetic exams and navigates to real document metadata', async () => {
    const user = userEvent.setup()
    portal()
    const document = await screen.findByRole('link', { name: 'Panel de laboratorio · DEMO' })
    expect(screen.getByText(es.demoNotice)).toBeInTheDocument()
    await user.click(document)
    expect(
      await screen.findByRole('heading', { name: 'Información del documento' }),
    ).toBeInTheDocument()
    expect(screen.getByText('synthetic-document-01.pdf')).toBeInTheDocument()
    expect(screen.getByText(es.detailNotice)).toBeInTheDocument()
  })
  it('uses cursor pagination and resets to the first page after filtering', async () => {
    const user = userEvent.setup()
    portal()
    await screen.findByRole('link', { name: 'Panel de laboratorio · DEMO' })
    await user.click(screen.getByRole('button', { name: es.next }))
    await screen.findByRole('link', { name: 'Documento anterior · DEMO' })
    expect(screen.getByText('Página 2')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText(es.filterStatus), 'rejected')
    await screen.findByText(es.emptyTitle)
    expect(screen.getByText('Página 1')).toBeInTheDocument()
  })
  it('blocks the clinical route after switching to patient demonstration', async () => {
    const user = userEvent.setup()
    portal('/clinical')
    await screen.findByRole('heading', { name: es.clinicalTitle })
    await user.selectOptions(screen.getByLabelText(es.demoRole), 'patient')
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(es.forbidden))
    await user.click(screen.getByRole('link', { name: es.goHome }))
    expect(await screen.findByRole('heading', { name: es.overviewTitle })).toBeInTheDocument()
    expect(screen.queryByText('Lab score')).not.toBeInTheDocument()
  })
  it('renders a safe not-found state for an unknown exam', async () => {
    portal('/exams/does-not-exist')
    expect(await screen.findByRole('alert')).toHaveTextContent(es.error_404)
  })
})
