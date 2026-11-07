import { z } from 'zod'
import type { ConnectionStatus } from './connectivity'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly retryAfter: string | null = null,
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
    mutation?: { body: unknown; key: string },
  ): Promise<T> => {
    const accessToken = token()
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), timeoutMs)
    const combined = signal ? AbortSignal.any([signal, controller.signal]) : controller.signal
    try {
      const response = await fetch(`${base.replace(/\/$/, '')}${path}`, {
        method: mutation ? 'POST' : 'GET',
        body: mutation ? JSON.stringify(mutation.body) : undefined,
        signal: combined,
        cache: 'no-store',
        credentials: 'omit',
        redirect: 'error',
        headers: {
          Accept: 'application/json',
          ...(mutation
            ? { 'Content-Type': 'application/json', 'Idempotency-Key': mutation.key }
            : {}),
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
      })
      if (signal?.aborted) throw signal.reason
      if (!response.ok) {
        if (response.status === 401) unauthorized(accessToken)
        let code = 'REQUEST_FAILED'
        // Only bounded machine codes are retained; never reflect clinical error text.
        if (response.status === 409)
          try {
            const error = z
              .object({
                detail: z.object({
                  code: z.enum(['EXTRACTION_NOT_READY', 'INVALID_CLINICAL_DATE']),
                }),
              })
              .safeParse(await response.json())
            if (error.success) code = error.data.detail.code
          } catch {
            if (combined.aborted) throw combined.reason
          }
        report(response.status >= 500 ? 'unavailable' : 'online')
        throw new ApiError(response.status, code, response.headers.get('Retry-After'))
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
