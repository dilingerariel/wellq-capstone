import { ApiError } from '../../services/http'
import type { ReviewRequest, ClinicianValidationRequest } from '../../types/api.generated'
import {
  bodyFor,
  createDraft,
  type Action,
  type ClinicianApi,
  type ClinicalDocument,
  type ClinicalDraft,
  type ClinicalExtraction,
} from './model'
type Phase =
  | 'idle'
  | 'loading'
  | 'editing'
  | 'preview'
  | 'sending'
  | 'uncertain'
  | 'conflict'
  | 'done'
  | 'error'
interface State {
  id: string
  patient: string
  phase: Phase
  document?: ClinicalDocument
  extraction?: ClinicalExtraction
  draft: ClinicalDraft
  action?: Action
  error?: string
  issues: { marker_code: string; code: string }[]
  retryAt: number
  extractionUnavailable: boolean
}
const initial = (): State => ({
  id: '',
  patient: '',
  phase: 'idle',
  draft: createDraft(),
  issues: [],
  retryAt: 0,
  extractionUnavailable: false,
})
export class ClinicianController {
  private state = initial()
  private listeners = new Set<() => void>()
  private flight?: AbortController
  private generation = 0
  private pending?: { action: Action; body: ReviewRequest | ClinicianValidationRequest }
  constructor(
    private api: ClinicianApi,
    private policy: () => { allowed: boolean; clinician: string; permissions: string[] },
    private verify: () => Promise<boolean>,
    private invalidate: () => void,
  ) {}
  getSnapshot = () => this.state
  subscribe = (fn: () => void) => {
    this.listeners.add(fn)
    return () => {
      this.listeners.delete(fn)
    }
  }
  private set(s: Partial<State>) {
    this.state = { ...this.state, ...s }
    this.listeners.forEach((fn) => fn())
  }
  clear = () => {
    this.generation++
    this.flight?.abort()
    this.flight = undefined
    this.pending = undefined
    this.state = initial()
    this.listeners.forEach((fn) => fn())
  }
  suspend = () => {
    if (this.flight) {
      this.generation++
      this.flight.abort()
      this.flight = undefined
      this.set({
        phase: this.pending ? 'uncertain' : this.state.document ? 'editing' : 'error',
        error: 'clinicalPaused',
      })
    }
  }
  hasWork = () =>
    !!this.state.id &&
    (!!this.pending ||
      this.state.draft.reviewNote !== '' ||
      this.state.draft.clinicalNote !== '' ||
      JSON.stringify(this.state.draft.markers) !==
        JSON.stringify(createDraft(this.state.extraction).markers))
  update(draft: ClinicalDraft) {
    if (this.state.phase === 'editing' && !this.pending)
      this.set({ draft, error: undefined, issues: [] })
  }
  edit() {
    if (this.state.phase === 'preview') this.set({ phase: 'editing' })
  }
  private ensure(g: number, action?: Action) {
    const p = this.policy()
    if (
      g !== this.generation ||
      !p.allowed ||
      (action &&
        !p.permissions.includes(action === 'review' ? 'clinical:review' : 'extractions:validate'))
    )
      throw new DOMException('Unavailable', 'AbortError')
    return p
  }
  preview(action: Action) {
    try {
      if (this.state.phase !== 'editing' || !this.state.document) return
      this.ensure(this.generation, action)
      if (action === 'review' && this.state.document.review.status !== 'not_reviewed')
        throw new Error('DOCUMENT_NOT_READY')
      bodyFor(action, this.state.draft, this.state.extraction)
      this.set({ phase: 'preview', action, error: undefined, issues: [] })
    } catch (e) {
      this.set({ error: e instanceof Error ? e.message : 'clinicalInvalid' })
    }
  }
  private async read(g: number, s: AbortSignal) {
    this.ensure(g)
    const doc = await this.api.document(this.state.id, s)
    this.ensure(g)
    if (doc.clinical_test_id !== this.state.id || doc.patient_id !== this.state.patient)
      throw new ApiError(403, 'clinicalPatientMismatch')
    let ext: ClinicalExtraction | undefined
    try {
      ext = await this.api.extraction(this.state.id, s)
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 409 && e.code === 'EXTRACTION_NOT_READY')) throw e
    }
    this.ensure(g)
    if (ext && ext.clinical_test_id !== this.state.id) throw new ApiError(502, 'INVALID_RESPONSE')
    if (ext?.clinical_version && ext.clinical_version !== doc.clinical_version)
      throw new ApiError(409, 'CLINICAL_VERSION_CONFLICT')
    return { doc, ext }
  }
  private fail(e: unknown, g: number) {
    if (g !== this.generation) return
    const a = e instanceof ApiError ? e : null
    const delay = a?.retryAfter
    const ms =
      delay && /^\d+$/.test(delay)
        ? Number(delay) * 1000
        : delay
          ? Math.max(0, Date.parse(delay) - Date.now())
          : 0
    this.set({
      phase:
        a?.status === 409 || a?.status === 428
          ? 'conflict'
          : this.pending
            ? 'uncertain'
            : this.state.document
              ? 'editing'
              : 'error',
      error: a
        ? a.code === 'REQUEST_FAILED'
          ? `reviewHttp${a.status}`
          : a.code
        : 'clinicalPaused',
      issues: a?.issues || [],
      retryAt: Date.now() + (Number.isFinite(ms) ? ms : 0),
    })
  }
  async load(id: string, patient: string) {
    if (this.flight || this.pending || Date.now() < this.state.retryAt) return
    if (this.state.id && (id !== this.state.id || patient !== this.state.patient)) return
    const ownSuccess = this.state.phase === 'done'
    this.set({ id, patient, phase: 'loading', error: undefined })
    const g = this.generation,
      c = new AbortController()
    this.flight = c
    try {
      if (!(await this.verify())) throw new Error('clinicalPaused')
      this.ensure(g)
      const { doc, ext } = await this.read(g, c.signal)
      if (
        this.hasWork() &&
        !ownSuccess &&
        (JSON.stringify(ext) !== JSON.stringify(this.state.extraction) ||
          JSON.stringify(doc) !== JSON.stringify(this.state.document))
      ) {
        this.set({ phase: 'conflict', error: 'clinicalConflict' })
        return
      }
      this.set({
        document: doc,
        extraction: ext,
        draft: this.hasWork() ? this.state.draft : createDraft(ext),
        phase: 'editing',
        extractionUnavailable: !ext,
      })
    } catch (e) {
      this.fail(e, g)
    } finally {
      if (g === this.generation) this.flight = undefined
    }
  }
  async send() {
    if (this.state.phase === 'uncertain' && this.pending?.action !== 'review') return
    if (
      this.flight ||
      Date.now() < this.state.retryAt ||
      !['preview', 'uncertain'].includes(this.state.phase) ||
      !this.state.action ||
      !this.state.document
    )
      return
    const action = this.state.action,
      g = this.generation,
      c = new AbortController()
    this.flight = c
    this.set({ phase: 'sending', error: undefined })
    try {
      if (!(await this.verify())) throw new Error('clinicalPaused')
      const p = this.ensure(g, action)
      const { doc, ext } = await this.read(g, c.signal)
      this.ensure(g, action)
      const replay =
        this.pending?.action === 'review' &&
        doc.review.status === 'reviewed' &&
        doc.review.reviewed_by === p.clinician
      if (
        !replay &&
        (JSON.stringify(doc) !== JSON.stringify(this.state.document) ||
          JSON.stringify(ext) !== JSON.stringify(this.state.extraction))
      ) {
        this.set({ phase: 'conflict', error: 'clinicalConflict' })
        return
      }
      if (
        doc.status !== 'ready_for_review' ||
        (action === 'review' && !replay && doc.review.status !== 'not_reviewed') ||
        (action !== 'review' && ext?.status !== 'confirmed')
      ) {
        this.set({ phase: 'conflict', error: 'clinicalConflict' })
        return
      }
      if (!doc.clinical_version) throw new ApiError(428, 'CLINICAL_VERSION_REQUIRED')
      this.pending ??= {
        action,
        body: {
          ...bodyFor(action, this.state.draft, this.state.extraction),
          expected_version: doc.clinical_version,
        },
      }
      if (action === 'review') {
        const result = await this.api.review(
          this.state.id,
          this.pending.body as ReviewRequest,
          c.signal,
        )
        this.ensure(g, action)
        if (
          result.clinical_test_id !== this.state.id ||
          result.patient_id !== this.state.patient ||
          result.review.status !== 'reviewed' ||
          result.review.reviewed_by !== p.clinician
        )
          throw new ApiError(502, 'INVALID_RESPONSE')
        this.set({ document: result })
      } else {
        const result = await this.api.validate(
          this.state.id,
          this.pending.body as ClinicianValidationRequest,
          c.signal,
        )
        this.ensure(g, action)
        if (
          result.clinical_test_id !== this.state.id ||
          result.extraction_id !== ext!.extraction_id ||
          result.status !== (action === 'validated' ? 'clinically_validated' : 'rejected')
        )
          throw new ApiError(502, 'INVALID_RESPONSE')
        this.set({ extraction: result })
      }
      this.pending = undefined
      this.set({
        phase: 'done',
        draft:
          action === 'review'
            ? { ...this.state.draft, reviewNote: '' }
            : { ...createDraft(this.state.extraction), reviewNote: this.state.draft.reviewNote },
      })
      this.invalidate()
    } catch (e) {
      if (
        g === this.generation &&
        e instanceof ApiError &&
        [403, 404, 409, 422, 428, 429].includes(e.status)
      )
        this.pending = undefined
      this.fail(e, g)
    } finally {
      if (g === this.generation) this.flight = undefined
    }
  }
  async reconcile() {
    // Validation is not idempotent: reconcile only, never automatically resend.
    if (this.pending?.action === 'review') {
      await this.send()
      return
    }
    if (this.flight || Date.now() < this.state.retryAt) return
    const g = this.generation,
      c = new AbortController()
    this.flight = c
    try {
      if (!(await this.verify())) throw new Error('clinicalPaused')
      const { doc, ext } = await this.read(g, c.signal)
      this.set({
        document: doc,
        extraction: ext,
        phase: 'conflict',
        error: 'clinicalUncertain',
        extractionUnavailable: !ext,
      })
      this.invalidate()
    } catch (e) {
      this.fail(e, g)
    } finally {
      if (g === this.generation) this.flight = undefined
    }
  }
}
