import { z } from 'zod'
import { statuses } from '../../types/clinical'
import type {
  CompleteUploadRequest,
  CompleteUploadResponse,
  InitiateUploadRequest,
  InitiateUploadResponse,
  RefreshUrlRequest,
  RefreshUrlResponse,
  UploadStatusResponse,
} from '../../types/api.generated'
import { ApiError, createHttp } from '../../services/http'

const signed = z.object({
  method: z.literal('PUT').default('PUT'),
  signed_url: z.string().url(),
  required_headers: z.record(z.string(), z.string()),
  expires_at: z.iso.datetime({ offset: true }),
})
const initiated = z.object({
  upload_id: z.string().min(1),
  clinical_test_id: z.string().min(1),
  status: z.enum(statuses).default('initiated'),
  upload: signed,
})
const refreshed = z.object({ upload_id: z.string(), status: z.enum(statuses), upload: signed })
const complete = z.object({
  clinical_test_id: z.string(),
  upload_id: z.string(),
  status: z.enum(statuses),
  local_file_can_be_deleted: z.boolean(),
  status_url: z.string(),
})
const status = z.object({
  clinical_test_id: z.string(),
  upload_id: z.string(),
  status: z.enum(statuses),
  processing: z.object({
    malware_scan: z.enum(['pending', 'passed', 'failed']),
    mime_validation: z.enum(['pending', 'passed', 'failed']),
  }),
  local_file_can_be_deleted: z.boolean(),
  error: z.record(z.string(), z.unknown()).nullable().optional(),
  completed_at: z.string().nullable().optional(),
})
export const extractionStates = [
  'queued',
  'extracting',
  'awaiting_confirmation',
  'confirmed',
  'clinically_validated',
  'extraction_failed',
  'unreadable',
  'discarded',
  'not_applicable',
  'rejected',
] as const
export type ExtractionState = (typeof extractionStates)[number]
export interface UploadApi {
  initiate(
    body: InitiateUploadRequest,
    key: string,
    signal: AbortSignal,
  ): Promise<InitiateUploadResponse>
  refresh(
    id: string,
    body: RefreshUrlRequest,
    key: string,
    signal: AbortSignal,
  ): Promise<RefreshUrlResponse>
  complete(
    id: string,
    body: CompleteUploadRequest,
    key: string,
    signal: AbortSignal,
  ): Promise<CompleteUploadResponse>
  status(id: string, signal: AbortSignal): Promise<UploadStatusResponse>
  extraction(id: string, signal: AbortSignal): Promise<{ status: ExtractionState }>
}
export function uploadApi(http: ReturnType<typeof createHttp>): UploadApi {
  const path = (id: string) => `/clinical-tests/uploads/${encodeURIComponent(id)}`
  return {
    initiate: (body, key, signal) =>
      http('/clinical-tests/uploads/initiate', initiated, signal, { body, key }),
    refresh: (id, body, key, signal) =>
      http(`${path(id)}/refresh-url`, refreshed, signal, { body, key }),
    complete: (id, body, key, signal) =>
      http(`${path(id)}/complete`, complete, signal, { body, key }),
    status: (id, signal) => http(`${path(id)}/status`, status, signal),
    extraction: (id, signal) =>
      http(
        `/clinical-tests/${encodeURIComponent(id)}/extraction`,
        z.object({ status: z.enum(extractionStates) }),
        signal,
      ),
  }
}
export interface TransferProgress {
  loaded: number
  total: number
}
export type Transfer = (
  file: File,
  descriptor: InitiateUploadResponse['upload'],
  signal: AbortSignal,
  progress: (value: TransferProgress) => void,
) => Promise<void>
export function storageTarget(descriptor: InitiateUploadResponse['upload']) {
  const url = new URL(descriptor.signed_url)
  const expiry = Date.parse(descriptor.expires_at)
  if (
    (descriptor.method || 'PUT') !== 'PUT' ||
    url.username ||
    url.password ||
    url.hash ||
    url.origin === window.location.origin ||
    !['https:', 'http:'].includes(url.protocol) ||
    (url.protocol === 'http:' && !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname))
  )
    throw new ApiError(502, 'uploadInvalidStorage')
  if (!Number.isFinite(expiry) || expiry <= Date.now()) throw new ApiError(403, 'uploadExpiredUrl')
  for (const [key, value] of Object.entries(descriptor.required_headers)) {
    if (
      typeof value !== 'string' ||
      /[\r\n]/.test(value) ||
      !/^[A-Za-z0-9!#$%&'*+.^_`|~-]+$/.test(key) ||
      /^(authorization|cookie|cookie2|host|content-length|origin|referer|connection|transfer-encoding|expect|upgrade|accept-encoding|access-control-request-.*|proxy-.*|sec-.*)$/i.test(
        key,
      )
    )
      throw new ApiError(502, 'uploadInvalidStorage')
  }
  return url
}
/** Separate anonymous transport: no API client, bearer token, cookies or persistence. */
export const transferFile: Transfer = (file, descriptor, signal, progress) =>
  new Promise((resolve, reject) => {
    signal.throwIfAborted()
    const target = storageTarget(descriptor)
    const xhr = new XMLHttpRequest()
    const abort = () => xhr.abort()
    const finish = (error?: unknown) => {
      signal.removeEventListener('abort', abort)
      if (error) reject(error)
      else resolve()
    }
    xhr.open('PUT', target.href)
    xhr.withCredentials = false
    xhr.timeout = 120_000
    for (const [key, value] of Object.entries(descriptor.required_headers))
      xhr.setRequestHeader(key, String(value))
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) progress({ loaded: event.loaded, total: event.total })
    }
    xhr.onload = () => {
      if (signal.aborted) {
        finish(signal.reason)
        return
      }
      if (xhr.responseURL && new URL(xhr.responseURL).href !== target.href) {
        finish(new ApiError(502, 'uploadInvalidStorage'))
        return
      }
      finish(
        xhr.status >= 200 && xhr.status < 300
          ? undefined
          : new ApiError(xhr.status, 'uploadPutFailed'),
      )
    }
    xhr.onerror = () => finish(new ApiError(0, 'uploadPutFailed'))
    xhr.ontimeout = () => finish(new ApiError(0, 'REQUEST_TIMEOUT'))
    xhr.onabort = () => finish(signal.reason || new DOMException('Aborted', 'AbortError'))
    signal.addEventListener('abort', abort, { once: true })
    if (signal.aborted) {
      finish(signal.reason)
      return
    }
    xhr.send(file)
  })
