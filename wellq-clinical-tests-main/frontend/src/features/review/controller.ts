import { ApiError } from '../../services/http'
import type { Exam } from '../../types/clinical'
import type { PatientConfirmationRequest } from '../../types/api.generated'
import { draftFor, payloadFor, type Draft, type Extraction, type ReviewApi } from './model'
type Phase =
  | 'idle'
  | 'loading'
  | 'editing'
  | 'reviewing'
  | 'sending'
  | 'uncertain'
  | 'conflict'
  | 'done'
  | 'error'
interface State {
  id: string
  phase: Phase
  document?: Exam
  extraction?: Extraction
  draft?: Draft
  error?: string
  retryAt: number
}
export class ReviewController {
  private state: State = { id: '', phase: 'idle', retryAt: 0 }
  private listeners = new Set<() => void>()
  private flight?: AbortController
  private generation = 0
  private pending?: { body: PatientConfirmationRequest; key: string }
  constructor(
    private api: ReviewApi,
    private policy: () => { patient: string; allowed: boolean; confirm: boolean },
    private verify: () => Promise<boolean>,
  ) {}
  getSnapshot = () => this.state
  subscribe = (fn: () => void) => {
    this.listeners.add(fn)
    return () => {
      this.listeners.delete(fn)
    }
  }
  private set(value: Partial<State>) {
    this.state = { ...this.state, ...value }
    this.listeners.forEach((fn) => fn())
  }
  clear = () => {
    this.generation++
    this.flight?.abort()
    this.flight = undefined
    this.pending = undefined
    this.state = { id: '', phase: 'idle', retryAt: 0 }
    this.listeners.forEach((fn) => fn())
  }
  suspend = () => {
    if (this.flight) {
      this.generation++
      this.flight.abort()
      this.flight = undefined
      this.set({
        phase: this.pending ? 'uncertain' : this.state.extraction ? 'editing' : 'error',
        error: 'reviewPaused',
      })
    }
  }
  update(draft: Draft) {
    if (this.state.phase === 'editing' && !this.pending) this.set({ draft, error: undefined })
  }
  edit() {
    if (this.state.phase === 'reviewing' && !this.pending)
      this.set({ phase: 'editing', error: undefined })
  }
  review() {
    try {
      if (
        !this.state.extraction ||
        !this.state.draft ||
        this.state.phase !== 'editing' ||
        this.state.extraction.status !== 'awaiting_confirmation'
      )
        return
      payloadFor(this.state.extraction, this.state.draft)
      this.set({ phase: 'reviewing', error: undefined })
    } catch (e) {
      this.set({ error: e instanceof Error ? e.message : 'reviewInvalid' })
    }
  }
  private ensure(g: number, write = false) {
    const p = this.policy()
    if (g !== this.generation || !p.allowed || (write && !p.confirm))
      throw new DOMException('Unavailable', 'AbortError')
    return p
  }
  private async read(id: string, signal: AbortSignal, g: number) {
    const p = this.ensure(g)
    const doc = await this.api.document(id, signal)
    this.ensure(g)
    if (doc.clinical_test_id !== id || doc.patient_id !== p.patient)
      throw new ApiError(403, 'FORBIDDEN')
    if (doc.status !== 'ready_for_review')
      throw new ApiError(
        409,
        doc.status === 'failed'
          ? 'reviewUploadFailed'
          : doc.status === 'rejected'
            ? 'reviewUploadRejected'
            : doc.status === 'deleted'
              ? 'reviewUploadDeleted'
              : 'reviewDocumentUnavailable',
      )
    const ext = await this.api.extraction(id, signal)
    this.ensure(g)
    if (ext.clinical_test_id !== id) throw new ApiError(502, 'INVALID_RESPONSE')
    return { doc, ext }
  }
  private fail(error: unknown, g: number) {
    if (g !== this.generation) return
    const api = error instanceof ApiError ? error : null
    const retry = api?.retryAfter
    const seconds =
      retry && /^\d+$/.test(retry)
        ? Number(retry) * 1000
        : retry
          ? Math.max(0, Date.parse(retry) - Date.now())
          : 0
    this.set({
      phase:
        api?.status === 409
          ? 'conflict'
          : this.pending
            ? 'uncertain'
            : this.state.extraction
              ? 'editing'
              : 'error',
      error:
        api?.code && api.code !== 'REQUEST_FAILED'
          ? api.code
          : api
            ? `reviewHttp${api.status}`
            : 'reviewPaused',
      retryAt: Date.now() + (Number.isFinite(seconds) ? seconds : 0),
    })
  }
  async load(id: string, replace = false) {
    if (this.flight || Date.now() < this.state.retryAt) return
    if (id !== this.state.id) {
      if (this.state.draft) return
      this.clear()
      this.set({ id })
    }
    if (this.pending) return
    const g = this.generation,
      c = new AbortController()
    this.flight = c
    this.set({ phase: 'loading', error: undefined })
    try {
      if (!(await this.verify())) throw new DOMException('Unavailable', 'AbortError')
      this.ensure(g)
      const { doc, ext } = await this.read(id, c.signal, g)
      if (
        this.state.extraction &&
        !replace &&
        JSON.stringify(ext) !== JSON.stringify(this.state.extraction)
      ) {
        this.set({ phase: 'conflict', error: 'reviewConflict' })
        return
      }
      this.set({
        document: doc,
        extraction: ext,
        draft: replace || !this.state.draft ? draftFor(ext) : this.state.draft,
        phase:
          ext.status === 'confirmed' || ext.status === 'clinically_validated' ? 'done' : 'editing',
      })
    } catch (e) {
      this.fail(e, g)
    } finally {
      if (g === this.generation) this.flight = undefined
    }
  }
  async confirm() {
    if (
      this.flight ||
      Date.now() < this.state.retryAt ||
      !['reviewing', 'uncertain'].includes(this.state.phase) ||
      !this.state.extraction ||
      !this.state.draft
    )
      return
    const g = this.generation,
      c = new AbortController()
    this.flight = c
    this.set({ phase: 'sending', error: undefined })
    try {
      if (!(await this.verify())) throw new DOMException('Unavailable', 'AbortError')
      this.ensure(g, true)
      const { doc, ext } = await this.read(this.state.id, c.signal, g)
      this.ensure(g, true)
      if (
        ext.extraction_id !== this.state.extraction.extraction_id ||
        (ext.status === 'awaiting_confirmation' &&
          (JSON.stringify(ext) !== JSON.stringify(this.state.extraction) ||
            doc.updated_at !== this.state.document?.updated_at)) ||
        (!this.pending && ext.status !== 'awaiting_confirmation') ||
        (this.pending &&
          !['awaiting_confirmation', 'confirmed', 'clinically_validated'].includes(ext.status))
      ) {
        this.set({ phase: 'conflict', error: 'reviewConflict' })
        return
      }
      this.pending ??= {
        body: payloadFor(this.state.extraction, this.state.draft),
        key: crypto.randomUUID(),
      }
      const result = await this.api.confirm(
        this.state.id,
        this.pending.body,
        this.pending.key,
        c.signal,
      )
      this.ensure(g, true)
      if (
        result.extraction_id !== ext.extraction_id ||
        result.clinical_test_id !== this.state.id ||
        !['confirmed', 'clinically_validated'].includes(result.status)
      )
        throw new ApiError(502, 'INVALID_RESPONSE')
      this.pending = undefined
      this.set({ extraction: result, draft: undefined, phase: 'done' })
    } catch (e) {
      // Definitive validation refusals did not commit; edits may be corrected.
      if (g === this.generation && e instanceof ApiError && e.status === 422)
        this.pending = undefined
      this.fail(e, g)
    } finally {
      if (g === this.generation) this.flight = undefined
    }
  }
}
