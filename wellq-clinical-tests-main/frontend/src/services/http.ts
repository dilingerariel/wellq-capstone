import { z } from 'zod'
import type { ConnectionStatus } from './connectivity'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly retryAfter: string | null = null,
    public readonly issues: { marker_code: string; code: string }[] = [],
    public readonly reason: string | null = null,
  ) {
    super(code)
    this.name = 'ApiError'
  }
}
export function createHttp(
  base: string,
  token: () => string | undefined,
  unauthorized: (token?: string) => void,
  report: (status: ConnectionStatus) => void = () => {},
  timeoutMs = 15_000,
) {
  const url = new URL(base, window.location.origin)
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  )
    throw new Error('Invalid API base URL')
  if (url.protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))
    throw new Error('HTTPS required for remote API')
  return async <T>(
    path: string,
    schema: z.ZodType<T>,
    signal?: AbortSignal,
    mutation?: { body: unknown; key?: string; method?: 'POST' | 'PATCH' },
  ): Promise<T> => {
    const accessToken = token()
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), timeoutMs)
    const combined = signal ? AbortSignal.any([signal, controller.signal]) : controller.signal
    try {
      const response = await fetch(`${base.replace(/\/$/, '')}${path}`, {
        method: mutation ? mutation.method || 'POST' : 'GET',
        body: mutation ? JSON.stringify(mutation.body) : undefined,
        signal: combined,
        cache: 'no-store',
        credentials: 'omit',
        redirect: 'error',
        headers: {
          Accept: 'application/json',
          ...(mutation
            ? {
                'Content-Type': 'application/json',
                ...(mutation.key ? { 'Idempotency-Key': mutation.key } : {}),
              }
            : {}),
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
      })
      if (signal?.aborted) throw signal.reason
      if (!response.ok) {
        if (response.status === 401) unauthorized(accessToken)
        let code = 'REQUEST_FAILED'
        let reason: string | null = null
        let issues: { marker_code: string; code: string }[] = []
        // Only bounded machine codes are retained; never reflect clinical error text.
        if ([404, 409, 422, 428, 502, 503].includes(response.status))
          try {
            const error = z
              .object({
                detail: z.object({
                  code: z.enum([
                    'NO_SCORE_AVAILABLE',
                    'EXPORT_SOURCE_CHANGED',
                    'EXPORT_VERSION_REQUIRED',
                    'EXPORT_IN_PROGRESS',
                    'EXPORT_ATTEMPT_EXPIRED',
                    'EXPORT_ATTEMPT_FAILED',
                    'PDF_GENERATION_FAILED',
                    'STORAGE_ERROR',
                    'PDF_ENGINE_UNAVAILABLE',
                    'CLINICAL_VERSION_REQUIRED',
                    'CLINICAL_VERSION_CONFLICT',
                    'EXTRACTION_NOT_READY',
                    'EXTRACTION_PROCESSING_FAILED',
                    'INVALID_CLINICAL_DATE',
                    'EXTRACTION_SUPERSEDED',
                    'IDEMPOTENCY_CONFLICT',
                    'INVALID_EXTRACTION_STATE',
                    'IDENTITY_CONFIRMATION_REQUIRED',
                    'LOW_CONFIDENCE_REVIEW_REQUIRED',
                    'INVALID_MARKER_EDIT',
                    'INCOMPLETE_MARKER_EDIT',
                    'REFERENCE_UNIT_MISMATCH',
                    'UNKNOWN_MARKER',
                    'UNIT_NOT_SUPPORTED',
                    'VALUE_INVALID_FORMAT',
                    'VALUE_IMPLAUSIBLE',
                    'RETRYABLE_CONFLICT',
                    'DOCUMENT_NOT_READY',
                    'NOT_CONFIRMED',
                    'INVALID_MARKER_CORRECTIONS',
                    'INVALID_VALIDATION_STATUS',
                  ]),
                  reason: z.enum(['insufficient_coverage', 'no_confirmed_exams']).optional(),
                  errors: z
                    .array(
                      z.object({
                        marker_code: z.string().max(200),
                        code: z.enum([
                          'DUPLICATE_CORRECTION',
                          'MARKER_NOT_IN_EXAM',
                          'UNKNOWN_MARKER',
                          'UNIT_NOT_SUPPORTED',
                          'VALUE_INVALID_FORMAT',
                          'VALUE_IMPLAUSIBLE',
                        ]),
                      }),
                    )
                    .max(1000)
                    .optional(),
                }),
              })
              .safeParse(await response.json())
            if (error.success) {
              code = error.data.detail.code
              issues = error.data.detail.errors || []
              reason = error.data.detail.reason || null
            }
          } catch {
            if (combined.aborted) throw combined.reason
          }
        report(response.status >= 500 ? 'unavailable' : 'online')
        throw new ApiError(
          response.status,
          code,
          response.headers.get('Retry-After'),
          issues,
          reason,
        )
      }
      let body: unknown
      try {
        body = await response.json()
      } catch {
        if (combined.aborted) throw combined.reason
        throw new ApiError(502, 'INVALID_RESPONSE')
      }
      const parsed = schema.safeParse(body)
      if (!parsed.success) throw new ApiError(502, 'INVALID_RESPONSE')
      if (combined.aborted) throw combined.reason
      report('online')
      return parsed.data
    } catch (error) {
      if (signal?.aborted) throw signal.reason
      if (error instanceof ApiError) throw error
      const status = !navigator.onLine
        ? 'offline'
        : controller.signal.aborted
          ? 'timeout'
          : 'unreachable'
      report(status)
      throw new ApiError(0, status === 'timeout' ? 'REQUEST_TIMEOUT' : 'NETWORK_UNAVAILABLE')
    } finally {
      window.clearTimeout(timer)
    }
  }
}
