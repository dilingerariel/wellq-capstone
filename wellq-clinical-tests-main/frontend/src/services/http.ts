import { z } from 'zod'

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
  unauthorized: () => void,
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
  return async <T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> => {
    const accessToken = token()
    let response: Response
    try {
      response = await fetch(`${base.replace(/\/$/, '')}${path}`, {
        signal,
        cache: 'no-store',
        credentials: 'omit',
        redirect: 'error',
        headers: {
          Accept: 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
      })
    } catch (error) {
      if (signal?.aborted) throw error
      throw new ApiError(0, 'NETWORK_UNAVAILABLE')
    }
    if (!response.ok) {
      if (response.status === 401) unauthorized()
      // Do not render arbitrary server messages, validation inputs or clinical bodies.
      throw new ApiError(response.status, 'REQUEST_FAILED', response.headers.get('Retry-After'))
    }
    try {
      return schema.parse(await response.json())
    } catch {
      throw new ApiError(502, 'INVALID_RESPONSE')
    }
  }
}
