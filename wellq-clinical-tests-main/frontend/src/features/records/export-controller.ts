import { ApiError } from '../../services/http'
import {
  fingerprint,
  readPdf,
  savePdf,
  validDownload,
  type Report,
  type ReportingApi,
  type ReportParams,
  type ExportResult,
} from './model'

type Phase =
  | 'idle'
  | 'generating'
  | 'ready'
  | 'pending'
  | 'uncertain'
  | 'downloading'
  | 'downloaded'
  | 'stale'
  | 'failed'
  | 'error'
interface State {
  patient: string
  phase: Phase
  result?: ExportResult
  error?: string
  retryAt: number
}
const initial = (): State => ({ patient: '', phase: 'idle', retryAt: 0 })
export class ReportExportController {
  private state = initial()
  private listeners = new Set<() => void>()
  private generation = 0
  private flight?: AbortController
  private plan?: {
    patient: string
    params: ReportParams
    version: string
    fingerprint: string
    key: string
  }
  constructor(
    private api: ReportingApi,
    private allowed: () => boolean,
    private verify: () => Promise<boolean>,
    private read = readPdf,
    private save = savePdf,
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
    this.plan = undefined
    this.state = initial()
    this.listeners.forEach((fn) => fn())
  }
  suspend = () => {
    if (!this.flight) return
    this.generation++
    this.flight.abort()
    this.flight = undefined
    this.set({ phase: 'uncertain', result: undefined, error: 'recordsExportUncertain' })
  }
  private ensure(g: number) {
    if (g !== this.generation || !this.allowed())
      throw new DOMException('Unavailable', 'AbortError')
  }
  private fail(error: unknown, g: number) {
    if (g !== this.generation) return
    const a = error instanceof ApiError ? error : null
    const stale = a?.code === 'EXPORT_SOURCE_CHANGED'
    const terminal = [
      'EXPORT_ATTEMPT_FAILED',
      'EXPORT_ATTEMPT_EXPIRED',
      'IDEMPOTENCY_CONFLICT',
      'STORAGE_ERROR',
      'PDF_GENERATION_FAILED',
      'PDF_ENGINE_UNAVAILABLE',
    ].includes(a?.code || '')
    const seconds = a?.retryAfter && /^\d+$/.test(a.retryAfter) ? Number(a.retryAfter) * 1000 : 0
    const wait = seconds || (a?.retryAfter ? Math.max(0, Date.parse(a.retryAfter) - Date.now()) : 0)
    this.set({
      phase: stale
        ? 'stale'
        : terminal
          ? 'failed'
          : ['DOWNLOAD_EXPIRED', 'EXPORT_IN_PROGRESS'].includes(a?.code || '')
            ? 'pending'
            : a && [403, 404, 422, 428].includes(a.status)
              ? 'error'
              : 'uncertain',
      error:
        a?.code === 'REQUEST_FAILED'
          ? `reviewHttp${a.status}`
          : a?.code || 'recordsExportUncertain',
      result: undefined,
      retryAt: Number.isFinite(wait) && wait > 0 ? Date.now() + wait : 0,
    })
  }
  async prepare(patient: string, params: ReportParams, displayed: Report) {
    if (
      this.flight ||
      Date.now() < this.state.retryAt ||
      ['stale', 'failed'].includes(this.state.phase)
    )
      return
    const g = this.generation,
      c = new AbortController()
    this.flight = c
    this.set({ patient, phase: 'generating', error: undefined, result: undefined })
    try {
      if (!(await this.verify())) throw new Error('Identity unverified')
      this.ensure(g)
      const before = await this.api.report(patient, params, c.signal)
      this.ensure(g)
      const hash = fingerprint(before)
      if (before.header.patient_id !== patient || fingerprint(displayed) !== hash)
        throw new ApiError(409, 'EXPORT_SOURCE_CHANGED')
      if (
        this.plan &&
        (this.plan.patient !== patient ||
          JSON.stringify(params) !== JSON.stringify(this.plan.params) ||
          hash !== this.plan.fingerprint)
      )
        throw new ApiError(409, 'EXPORT_SOURCE_CHANGED')
      this.plan ??= {
        patient,
        params: structuredClone(params),
        version: before.source_version,
        fingerprint: hash,
        key: crypto.randomUUID(),
      }
      const result = await this.api.export(
        patient,
        { ...this.plan.params, expected_source_version: this.plan.version },
        this.plan.key,
        c.signal,
      )
      this.ensure(g)
      if (result.source_version !== this.plan.version)
        throw new ApiError(409, 'EXPORT_SOURCE_CHANGED')
      if (result.patient_id !== patient) throw new ApiError(403, 'RECORD_PATIENT_MISMATCH')
      const after = await this.api.report(patient, params, c.signal)
      this.ensure(g)
      if (fingerprint(after) !== hash) throw new ApiError(409, 'EXPORT_SOURCE_CHANGED')
      if (result.status === 'ready') validDownload(result)
      this.set({
        phase: result.status === 'ready' ? 'ready' : 'pending',
        result,
        error: result.status === 'download_pending' ? 'recordsSignerPending' : undefined,
      })
    } catch (e) {
      this.fail(e, g)
    } finally {
      if (g === this.generation) this.flight = undefined
    }
  }
  async download() {
    if (this.flight || !this.plan || !this.state.result || this.state.phase !== 'ready') return
    const g = this.generation,
      c = new AbortController(),
      plan = this.plan,
      result = this.state.result
    this.flight = c
    this.set({ phase: 'downloading', error: undefined })
    try {
      if (!(await this.verify())) throw new Error('Identity unverified')
      this.ensure(g)
      validDownload(result)
      const current = await this.api.report(plan.patient, plan.params, c.signal)
      this.ensure(g)
      if (fingerprint(current) !== plan.fingerprint)
        throw new ApiError(409, 'EXPORT_SOURCE_CHANGED')
      const bytes = await this.read(result, c.signal)
      this.ensure(g)
      // Replay binds these bytes to the persisted full server source, including
      // fields omitted by the display projection. No new export key is created.
      const checked = await this.api.export(
        plan.patient,
        { ...plan.params, expected_source_version: plan.version },
        plan.key,
        c.signal,
      )
      this.ensure(g)
      if (
        checked.source_version !== plan.version ||
        !checked.replayed ||
        checked.patient_id !== plan.patient ||
        checked.export_id !== result.export_id ||
        checked.sha256 !== result.sha256 ||
        checked.size_bytes !== result.size_bytes
      )
        throw new ApiError(409, 'EXPORT_SOURCE_CHANGED')
      this.save(bytes, result.file_name)
      this.set({ phase: 'downloaded', result: undefined })
    } catch (e) {
      this.fail(e, g)
    } finally {
      if (g === this.generation) this.flight = undefined
    }
  }
}
