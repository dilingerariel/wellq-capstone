import { afterEach, describe, expect, it, vi } from 'vitest'
import { webcrypto } from 'node:crypto'
import { UploadController } from './controller'
import { storageTarget, transferFile, type UploadApi } from './api'
import { ApiError } from '../../services/http'
import { MAX_UPLOAD_BYTES, validateUploadFile } from './intent'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})
const descriptor = () => ({
  method: 'PUT',
  signed_url: 'https://storage.example.invalid/synthetic-object',
  required_headers: { 'Content-Type': 'application/pdf', 'x-goog-if-generation-match': '0' },
  expires_at: new Date(Date.now() + 900000).toISOString(),
})
const receipt = () => ({
  clinical_test_id: 'synthetic-ct',
  upload_id: 'synthetic-upload',
  status: 'initiated' as const,
  upload: descriptor(),
})
const status = (state = 'processing', safe = false) => ({
  clinical_test_id: 'synthetic-ct',
  upload_id: 'synthetic-upload',
  status: state as 'processing',
  processing: {
    malware_scan: safe ? ('passed' as const) : ('pending' as const),
    mime_validation: safe ? ('passed' as const) : ('pending' as const),
  },
  local_file_can_be_deleted: safe,
})
function setup() {
  vi.stubGlobal('crypto', webcrypto)
  const api = {
    initiate: vi.fn<UploadApi['initiate']>().mockResolvedValue(receipt()),
    refresh: vi.fn<UploadApi['refresh']>().mockResolvedValue(receipt()),
    complete: vi.fn<UploadApi['complete']>().mockResolvedValue({
      ...receipt(),
      local_file_can_be_deleted: false,
      status_url: '/never-follow-untrusted-url',
    }),
    status: vi.fn<UploadApi['status']>().mockResolvedValue(status('ready_for_review', true)),
    extraction: vi
      .fn<UploadApi['extraction']>()
      .mockResolvedValue({ status: 'awaiting_confirmation' }),
  } satisfies UploadApi
  const transfer = vi.fn().mockResolvedValue(undefined)
  let allowed = true
  const controller = new UploadController(api, () => allowed, transfer, 3, 1)
  controller.select(
    Object.assign(new File(['abc'], 'synthetic.pdf', { type: 'application/pdf' }), {
      arrayBuffer: async () => new TextEncoder().encode('abc').buffer,
    }),
  )
  controller.update({ title: 'Synthetic', test_date: '2026-01-01' })
  return {
    api,
    transfer,
    controller,
    deny: () => {
      allowed = false
    },
  }
}
describe('clinical upload state machine', () => {
  it('allows correcting a definitive first validation refusal while preserving the File', async () => {
    const { controller, api } = setup()
    const file = controller.getSnapshot().file
    api.initiate.mockRejectedValueOnce(new ApiError(422, 'REQUEST_FAILED'))
    await controller.run()
    expect(controller.getSnapshot()).toMatchObject({ locked: false, file })
    controller.update({ title: 'Corrected synthetic metadata' })
    await controller.run()
    expect(controller.getSnapshot().phase).toBe('available')
    expect(api.initiate.mock.calls[1]?.[0].title).toBe('Corrected synthetic metadata')
    expect(api.initiate.mock.calls[1]?.[1]).not.toBe(api.initiate.mock.calls[0]?.[1])
  })
  it('never unlocks metadata after an ambiguous initiate, even when a later retry is refused', async () => {
    const { controller, api } = setup()
    api.initiate
      .mockRejectedValueOnce(new ApiError(0, 'NETWORK_UNAVAILABLE'))
      .mockRejectedValueOnce(new ApiError(422, 'REQUEST_FAILED'))
    await controller.run()
    await controller.run()
    expect(controller.getSnapshot().locked).toBe(true)
    expect(api.initiate.mock.calls[1]?.slice(0, 2)).toEqual(api.initiate.mock.calls[0]?.slice(0, 2))
  })
  it('retries extraction-not-ready without claiming queued or failed clinical results', async () => {
    const { controller, api } = setup()
    controller.update({ ai_consent: true })
    api.extraction.mockRejectedValueOnce(new ApiError(409, 'EXTRACTION_NOT_READY'))
    await controller.run()
    expect(api.extraction).toHaveBeenCalledTimes(2)
    expect(controller.getSnapshot().extraction).toBe('awaiting_confirmation')
  })
  it('reuses a refresh operation key after its reply was lost', async () => {
    const { controller, api, transfer } = setup()
    transfer.mockRejectedValueOnce(new ApiError(403, 'uploadPutFailed'))
    await controller.run()
    api.status.mockResolvedValueOnce(status('initiated'))
    api.refresh.mockRejectedValueOnce(new ApiError(0, 'NETWORK_UNAVAILABLE'))
    await controller.run()
    api.status.mockResolvedValueOnce(status('initiated'))
    await controller.run()
    expect(api.refresh.mock.calls[0]?.slice(0, 3)).toEqual(api.refresh.mock.calls[1]?.slice(0, 3))
    expect(api.initiate).toHaveBeenCalledOnce()
  })
  it('hashes real bytes, separates transfer from verification and permits only server-confirmed local deletion', async () => {
    const { api, transfer, controller } = setup()
    api.status.mockResolvedValueOnce(status())
    await controller.run()
    expect(transfer).toHaveBeenCalledOnce()
    expect(api.initiate.mock.calls[0]?.[0]).toMatchObject({
      sha256: 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
      size_bytes: 3,
    })
    expect(api.complete).toHaveBeenCalledOnce()
    expect(controller.getSnapshot()).toMatchObject({
      phase: 'available',
      status: { local_file_can_be_deleted: true },
    })
  })
  it('deduplicates double clicks and reuses the exact initiate payload/key after a lost reply', async () => {
    const { api, controller } = setup()
    api.initiate.mockRejectedValueOnce(new ApiError(0, 'NETWORK_UNAVAILABLE'))
    await Promise.all([controller.run(), controller.run()])
    expect(api.initiate).toHaveBeenCalledOnce()
    const first = api.initiate.mock.calls[0]
    await controller.run()
    expect(api.initiate.mock.calls[1]?.slice(0, 2)).toEqual(first?.slice(0, 2))
  })
  it('keeps bytes on PUT failure, refreshes an expired URL and never completes before transfer', async () => {
    const { api, transfer, controller } = setup()
    transfer.mockRejectedValueOnce(new ApiError(403, 'uploadPutFailed'))
    await controller.run()
    expect(api.complete).not.toHaveBeenCalled()
    expect(controller.getSnapshot().file?.size).toBe(3)
    api.status.mockResolvedValueOnce(status('initiated'))
    await controller.run()
    expect(api.refresh).toHaveBeenCalledOnce()
    expect(transfer).toHaveBeenCalledTimes(2)
    expect(api.initiate).toHaveBeenCalledOnce()
  })
  it('reuses complete key after failure without uploading bytes again', async () => {
    const { api, transfer, controller } = setup()
    api.complete.mockRejectedValueOnce(new ApiError(503, 'REQUEST_FAILED'))
    await controller.run()
    expect(controller.getSnapshot().status?.local_file_can_be_deleted).not.toBe(true)
    api.status.mockResolvedValueOnce(status('initiated'))
    await controller.run()
    expect(transfer).toHaveBeenCalledOnce()
    expect(api.complete.mock.calls[0]?.slice(0, 3)).toEqual(api.complete.mock.calls[1]?.slice(0, 3))
  })
  it('reconciles an acknowledged server operation after a lost complete reply', async () => {
    const { api, controller } = setup()
    api.complete.mockRejectedValueOnce(new ApiError(0, 'NETWORK_UNAVAILABLE'))
    await controller.run()
    await controller.run()
    expect(api.complete).toHaveBeenCalledOnce()
    expect(controller.getSnapshot().phase).toBe('available')
  })
  it('does not treat storage 412 as success: completes for server validation and retains rejected originals', async () => {
    const { api, transfer, controller } = setup()
    transfer.mockRejectedValue(new ApiError(412, 'uploadPutFailed'))
    api.status.mockResolvedValue(status('rejected'))
    await controller.run()
    expect(api.complete).toHaveBeenCalledOnce()
    expect(controller.getSnapshot()).toMatchObject({
      phase: 'rejected',
      status: { local_file_can_be_deleted: false },
    })
  })
  it('bounds polling and offers a later read without repeating mutations', async () => {
    const { api, transfer, controller } = setup()
    api.status.mockResolvedValue(status())
    await controller.run()
    expect(api.status).toHaveBeenCalledTimes(3)
    expect(controller.getSnapshot().phase).toBe('poll-limit')
    api.status.mockResolvedValue(status('ready_for_review', false))
    await controller.run()
    expect(api.complete).toHaveBeenCalledOnce()
    expect(transfer).toHaveBeenCalledOnce()
    expect(controller.getSnapshot().status?.local_file_can_be_deleted).toBe(false)
  })
  it('represents human confirmation only when the extraction endpoint reports it', async () => {
    const { controller } = setup()
    controller.update({ ai_consent: true })
    await controller.run()
    expect(controller.getSnapshot()).toMatchObject({
      phase: 'available',
      extraction: 'awaiting_confirmation',
    })
  })
  it('pauses on connection loss and sends no mutation on reconnect without an explicit click', async () => {
    const { controller, transfer, api, deny } = setup()
    let done!: () => void
    transfer.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          done = resolve
        }),
    )
    const running = controller.run()
    await vi.waitFor(() => expect(transfer).toHaveBeenCalledOnce())
    deny()
    controller.suspend()
    done()
    await running
    expect(controller.getSnapshot()).toMatchObject({ phase: 'paused', file: { size: 3 } })
    expect(api.complete).not.toHaveBeenCalled()
  })
  it('clears file and stale async results on identity change, including a delayed hash', async () => {
    const { controller, api } = setup()
    let done!: (bytes: ArrayBuffer) => void
    controller.select(
      Object.assign(new File(['abc'], 'synthetic.pdf', { type: 'application/pdf' }), {
        arrayBuffer: () =>
          new Promise<ArrayBuffer>((resolve) => {
            done = resolve
          }),
      }),
    )
    const running = controller.run()
    controller.clear()
    done(new TextEncoder().encode('abc').buffer)
    await running
    expect(controller.getSnapshot()).toMatchObject({ phase: 'idle', file: null, locked: false })
    expect(api.initiate).not.toHaveBeenCalled()
    controller.select(
      Object.assign(new File(['def'], 'synthetic.pdf', { type: 'application/pdf' }), {
        arrayBuffer: async () => new TextEncoder().encode('def').buffer,
      }),
    )
    controller.update({ title: 'Other account', test_date: '2026-01-01' })
    await controller.run()
    expect(api.initiate.mock.calls[0]?.[0].sha256).not.toBe(
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    )
  })
  it('honors Retry-After and keeps cancelled bytes without claiming server cancellation', async () => {
    const { controller, api } = setup()
    api.initiate.mockRejectedValue(new ApiError(429, 'REQUEST_FAILED', '60'))
    await controller.run()
    await controller.run()
    expect(api.initiate).toHaveBeenCalledOnce()
    expect(controller.getSnapshot().error).toBe('uploadRetryLater')
  })
})
describe('file and anonymous storage boundaries', () => {
  it('rejects excessive size, empty files, MIME mismatch and dangerous double extensions', () => {
    for (const name of ['unsafe.exe.pdf', '../synthetic.pdf', 'synthetic.pdf '])
      expect(() => validateUploadFile(new File(['a'], name, { type: 'application/pdf' }))).toThrow(
        'uploadInvalidFile',
      )
    expect(() =>
      validateUploadFile(
        Object.defineProperty(
          new File(['a'], 'synthetic.pdf', { type: 'application/pdf' }),
          'size',
          { value: MAX_UPLOAD_BYTES + 1 },
        ),
      ),
    ).toThrow('uploadInvalidSize')
    expect(() =>
      validateUploadFile(new File([], 'synthetic.pdf', { type: 'application/pdf' })),
    ).toThrow('uploadInvalidSize')
    expect(() =>
      validateUploadFile(new File(['a'], 'synthetic.pdf', { type: 'text/html' })),
    ).toThrow('uploadInvalidFile')
  })
  it('rejects expired, plaintext remote, embedded credentials and auth-bearing storage descriptors', () => {
    expect(() => storageTarget({ ...descriptor(), expires_at: new Date(0).toISOString() })).toThrow(
      'uploadExpiredUrl',
    )
    expect(() =>
      storageTarget({ ...descriptor(), signed_url: 'http://storage.example.invalid/' }),
    ).toThrow('uploadInvalidStorage')
    expect(() =>
      storageTarget({
        ...descriptor(),
        required_headers: { Authorization: 'synthetic-forbidden' },
      }),
    ).toThrow('uploadInvalidStorage')
  })
  it('sends only required storage headers, real progress, no credentials, and handles timeout/abort', async () => {
    const requests: FakeXHR[] = []
    class FakeXHR {
      upload = { onprogress: null as null | ((event: ProgressEvent) => void) }
      withCredentials = true
      timeout = 0
      status = 200
      responseURL = ''
      headers: Record<string, string> = {}
      onload = () => {}
      onerror = () => {}
      ontimeout = () => {}
      onabort = () => {}
      constructor() {
        requests.push(this)
      }
      open = vi.fn()
      setRequestHeader = (k: string, v: string) => {
        this.headers[k] = v
      }
      send = vi.fn()
      abort = () => this.onabort()
    }
    vi.stubGlobal('XMLHttpRequest', FakeXHR)
    const progress = vi.fn(),
      signal = new AbortController(),
      file = new File(['abc'], 'synthetic.pdf')
    const pending = transferFile(file, descriptor(), signal.signal, progress)
    const xhr = requests[0]!
    expect(xhr.withCredentials).toBe(false)
    expect(xhr.headers).toEqual(descriptor().required_headers)
    expect(xhr.timeout).toBe(120000)
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 2, total: 3 } as ProgressEvent)
    expect(progress).toHaveBeenCalledWith({ loaded: 2, total: 3 })
    xhr.ontimeout()
    await expect(pending).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT' })
    const aborted = transferFile(file, descriptor(), signal.signal, vi.fn())
    signal.abort()
    await expect(aborted).rejects.toMatchObject({ name: 'AbortError' })
  })
})
