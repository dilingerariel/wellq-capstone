import type { InitiateUploadResponse, UploadStatusResponse } from '../../types/api.generated'
import { ApiError } from '../../services/http'
import {
  createUploadKeys,
  prepareUploadIntent,
  validateUploadFile,
  type UploadMetadata,
} from './intent'
import {
  transferFile,
  type UploadApi,
  type Transfer,
  type TransferProgress,
  type ExtractionState,
} from './api'

export type UploadPhase =
  | 'idle'
  | 'selected'
  | 'hashing'
  | 'initiating'
  | 'uploading'
  | 'transferred'
  | 'completing'
  | 'processing'
  | 'available'
  | 'rejected'
  | 'failed'
  | 'deleted'
  | 'paused'
  | 'cancelled'
  | 'poll-limit'
  | 'error'
const active = new Set<UploadPhase>([
  'hashing',
  'initiating',
  'uploading',
  'transferred',
  'completing',
  'processing',
])
export interface UploadState {
  file: File | null
  metadata: UploadMetadata
  phase: UploadPhase
  progress: TransferProgress | null
  locked: boolean
  error: string | null
  status: UploadStatusResponse | null
  extraction: ExtractionState | null
}
const initial = (): UploadState => ({
  file: null,
  metadata: { title: '', test_type: 'blood_test', test_date: '', ai_consent: false, notes: '' },
  phase: 'idle',
  progress: null,
  locked: false,
  error: null,
  status: null,
  extraction: null,
})
type Intent = Awaited<ReturnType<typeof prepareUploadIntent>>
/** One in-memory operation per identity boundary. No persistence or automatic mutation replay. */
export class UploadController {
  private state = initial()
  private listeners = new Set<() => void>()
  private generation = 0
  private operation: AbortController | null = null
  private intent: Intent | null = null
  private receipt: InitiateUploadResponse | null = null
  private putAccepted = false
  private initiateCouldExist = false
  private refresh: { key: string; descriptor: InitiateUploadResponse['upload'] | null } | null =
    null
  private retryAt = 0
  constructor(
    private api: UploadApi,
    private allowed: () => boolean,
    private transfer: Transfer = transferFile,
    private pollLimit = 20,
    private delayMs = 3000,
  ) {}
  getSnapshot = () => this.state
  subscribe = (listener: () => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }
  private commit(patch: Partial<UploadState>) {
    this.state = { ...this.state, ...patch }
    this.listeners.forEach((listener) => listener())
  }
  clear = () => {
    this.generation++
    this.operation?.abort()
    this.operation = null
    this.intent = null
    this.receipt = null
    this.putAccepted = false
    this.initiateCouldExist = false
    this.refresh = null
    this.retryAt = 0
    this.state = initial()
    this.listeners.forEach((listener) => listener())
  }
  select = (file: File) => {
    if (this.state.locked || this.busy) return
    try {
      validateUploadFile(file)
      this.commit({ file, phase: 'selected', error: null })
    } catch (error) {
      this.commit({
        file: null,
        phase: 'error',
        error: error instanceof Error ? error.message : 'uploadInvalidFile',
      })
    }
  }
  update = (patch: Partial<UploadMetadata>) => {
    if (!this.state.locked && !this.busy)
      this.commit({ metadata: { ...this.state.metadata, ...patch }, error: null })
  }
  get busy() {
    return this.operation !== null
  }
  cancel = (offline = false) => {
    if (!this.operation) return
    this.generation++
    this.operation.abort()
    this.operation = null
    this.commit({ phase: offline ? 'paused' : 'cancelled', error: null })
  }
  private ensure(generation: number, signal: AbortSignal) {
    signal.throwIfAborted()
    if (generation !== this.generation) throw new DOMException('Obsolete', 'AbortError')
    if (!this.allowed()) throw new ApiError(0, 'uploadConnectionRequired')
  }
  private async readStatus(generation: number, signal: AbortSignal) {
    this.ensure(generation, signal)
    const response = await this.api.status(this.receipt!.upload_id, signal)
    this.ensure(generation, signal)
    if (
      response.upload_id !== this.receipt!.upload_id ||
      response.clinical_test_id !== this.receipt!.clinical_test_id
    )
      throw new ApiError(502, 'INVALID_RESPONSE')
    this.commit({ status: response })
    return response
  }
  private async poll(generation: number, signal: AbortSignal) {
    for (let count = 0; count < this.pollLimit; count++) {
      const status = await this.readStatus(generation, signal)
      if (['rejected', 'failed', 'deleted'].includes(status.status)) {
        this.commit({ phase: status.status as 'rejected' | 'failed' | 'deleted' })
        return
      }
      if (status.status === 'ready_for_review') {
        if (this.intent?.body.ai_consent) {
          try {
            const extraction = await this.api.extraction(status.clinical_test_id, signal)
            this.ensure(generation, signal)
            this.commit({ extraction: extraction.status })
            if (!['queued', 'extracting'].includes(extraction.status)) {
              this.commit({ phase: 'available' })
              return
            }
          } catch (error) {
            this.ensure(generation, signal)
            if (
              !(error instanceof ApiError) ||
              error.status !== 409 ||
              error.code !== 'EXTRACTION_NOT_READY'
            )
              throw error
          }
        } else {
          this.commit({ phase: 'available' })
          return
        }
      }
      if (status.status === 'initiated') {
        this.commit({ phase: 'paused', error: 'uploadNotConfirmed' })
        return
      }
      this.commit({ phase: 'processing' })
      if (count === this.pollLimit - 1) break
      await new Promise<void>((resolve, reject) => {
        const abort = () => {
          clearTimeout(timer)
          reject(signal.reason)
        }
        const timer = setTimeout(
          () => {
            signal.removeEventListener('abort', abort)
            resolve()
          },
          Math.min(15_000, this.delayMs * 2 ** Math.floor(count / 4)),
        )
        signal.addEventListener('abort', abort, { once: true })
        if (signal.aborted) abort()
      })
    }
    this.commit({ phase: 'poll-limit' })
  }
  /** Explicit click only. A single flight owns every mutation and reuses its stable keys. */
  run = async () => {
    if (this.busy || !this.state.file || !this.allowed()) return
    if (Date.now() < this.retryAt) {
      this.commit({ error: 'uploadRetryLater' })
      return
    }
    const operation = new AbortController(),
      generation = ++this.generation,
      signal = operation.signal
    this.operation = operation
    this.commit({ error: null, progress: null })
    try {
      if (!this.intent) {
        this.commit({ phase: 'hashing' })
        const intent = await prepareUploadIntent(
          this.state.file,
          this.state.metadata,
          createUploadKeys(),
          signal,
        )
        this.ensure(generation, signal)
        this.intent = intent
        this.commit({ locked: true })
      }
      if (this.receipt) {
        const status = await this.readStatus(generation, signal)
        if (status.status !== 'initiated' && status.status !== 'object_uploaded') {
          await this.poll(generation, signal)
          return
        }
        if (status.status === 'object_uploaded') this.putAccepted = true
      } else {
        this.ensure(generation, signal)
        this.commit({ phase: 'initiating' })
        const uncertain = this.initiateCouldExist
        this.initiateCouldExist = true
        try {
          const response = await this.api.initiate(
            this.intent.body,
            this.intent.keys.initiateKey,
            signal,
          )
          this.ensure(generation, signal)
          this.receipt = response
        } catch (error) {
          // A first, definitive validation refusal created no upload. Permit correction
          // without dropping the File. Never unlock after an earlier ambiguous reply.
          if (
            !signal.aborted &&
            generation === this.generation &&
            !uncertain &&
            error instanceof ApiError &&
            [400, 413, 422].includes(error.status)
          ) {
            this.intent = null
            this.initiateCouldExist = false
            this.commit({ locked: false })
          }
          throw error
        }
      }
      if (!this.putAccepted) {
        this.ensure(generation, signal)
        let descriptor = this.receipt.upload
        // A retry always refreshes the old URL. A lost refresh reply reuses its key;
        // an acknowledged but now expired URL gets a new refresh operation key.
        if (this.state.status || Date.parse(descriptor.expires_at) <= Date.now() + 5000) {
          if (
            !this.refresh ||
            (this.refresh.descriptor &&
              Date.parse(this.refresh.descriptor.expires_at) <= Date.now() + 5000)
          )
            this.refresh = { key: crypto.randomUUID(), descriptor: null }
          if (!this.refresh.descriptor) {
            const renewed = await this.api.refresh(
              this.receipt.upload_id,
              {
                client_upload_id: this.intent.body.client_upload_id,
                sha256: this.intent.body.sha256,
              },
              this.refresh.key,
              signal,
            )
            this.ensure(generation, signal)
            if (renewed.upload_id !== this.receipt.upload_id || renewed.status !== 'initiated')
              throw new ApiError(409, 'uploadNotConfirmed')
            this.refresh.descriptor = renewed.upload
          }
          descriptor = this.refresh.descriptor
        }
        this.ensure(generation, signal)
        this.commit({ phase: 'uploading' })
        try {
          await this.transfer(this.state.file, descriptor, signal, (progress) => {
            if (generation === this.generation && !signal.aborted) this.commit({ progress })
          })
          this.ensure(generation, signal)
          this.commit({ phase: 'transferred' })
        } catch (error) {
          this.ensure(generation, signal)
          // Create-only storage may already have accepted bytes before a lost reply.
          // 412 is not upload success: only the worker can verify the existing bytes.
          if (!(error instanceof ApiError) || error.status !== 412) {
            if (error instanceof ApiError && error.status === 403 && this.refresh?.descriptor)
              this.refresh = null
            throw error
          }
        }
        this.putAccepted = true
      }
      this.ensure(generation, signal)
      this.commit({ phase: 'completing' })
      const completed = await this.api.complete(
        this.receipt.upload_id,
        {
          client_upload_id: this.intent.body.client_upload_id,
          sha256: this.intent.body.sha256,
          size_bytes: this.intent.body.size_bytes,
        },
        this.intent.keys.completeKey,
        signal,
      )
      this.ensure(generation, signal)
      if (
        completed.upload_id !== this.receipt.upload_id ||
        completed.clinical_test_id !== this.receipt.clinical_test_id
      )
        throw new ApiError(502, 'INVALID_RESPONSE')
      // Ignore status_url for transport: build the typed endpoint, never send a token to a returned arbitrary URL.
      await this.poll(generation, signal)
    } catch (error) {
      if (signal.aborted || generation !== this.generation) return
      const known = error instanceof ApiError
      const retry = known ? error.retryAfter : null
      if (retry) {
        const seconds = Number(retry)
        this.retryAt = Number.isFinite(seconds)
          ? Date.now() + Math.max(0, seconds) * 1000
          : Math.max(Date.now(), Date.parse(retry) || 0)
      }
      this.commit({
        phase: !this.allowed() ? 'paused' : 'error',
        error: known
          ? error.code === 'REQUEST_FAILED'
            ? `error_${error.status}`
            : error.code
          : 'uploadInvalidMetadata',
      })
    } finally {
      if (generation === this.generation) this.operation = null
      this.listeners.forEach((listener) => listener())
    }
  }
  suspend = () => {
    if (active.has(this.state.phase)) this.cancel(true)
  }
}
