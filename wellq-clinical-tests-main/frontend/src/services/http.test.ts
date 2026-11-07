import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { createHttp } from './http'
import { apiSource } from './clinical'
afterEach(() => vi.unstubAllGlobals())
describe('HTTP boundary', () => {
  it.each([400, 401, 403, 404, 409, 422, 429, 500, 503])(
    'preserves status %s without reflecting sensitive response bodies',
    async (status) => {
      const unauthorized = vi.fn()
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          new Response(JSON.stringify({ detail: { message: 'synthetic-sensitive-body' } }), {
            status,
            headers: { 'Retry-After': '2' },
          }),
        ),
      )
      const http = createHttp('/api/v1', () => 'synthetic-external-token', unauthorized)
      await expect(http('/clinical-tests', z.unknown())).rejects.toMatchObject({
        status,
        code: 'REQUEST_FAILED',
        retryAfter: '2',
      })
      expect(unauthorized).toHaveBeenCalledTimes(status === 401 ? 1 : 0)
    },
  )
  it('rejects malformed successful data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })))
    await expect(
      createHttp(
        '/api/v1',
        () => undefined,
        vi.fn(),
      )('/x', z.object({ items: z.array(z.string()) })),
    ).rejects.toMatchObject({ status: 502 })
  })
  it('sends an opaque cursor, abort signal and auth header to the clinician route', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"items":[],"next_cursor":null}'))
    vi.stubGlobal('fetch', fetch)
    const controller = new AbortController()
    await apiSource('/api/v1', 'clinician', () => 'synthetic-external-token', vi.fn()).list(
      { cursor: 'opaque+/=', status: 'processing' },
      'synthetic-patient',
      controller.signal,
    )
    const [url, init] = fetch.mock.calls[0]!
    expect(url).toContain('/patients/synthetic-patient/clinical-tests?')
    expect(new URL(url, 'http://localhost').searchParams.get('cursor')).toBe('opaque+/=')
    expect(init).toMatchObject({
      signal: expect.any(AbortSignal),
      credentials: 'omit',
      cache: 'no-store',
      headers: { Authorization: ['Bearer', 'synthetic-external-token'].join(' ') },
    })
  })
  it('patient route ignores externally supplied patient IDs', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"items":[]}'))
    vi.stubGlobal('fetch', fetch)
    await apiSource('/api/v1', 'patient', () => undefined, vi.fn()).list({}, 'untrusted-id')
    expect(fetch.mock.calls[0]![0]).toBe('/api/v1/clinical-tests?limit=6')
  })
  it('does not fall back to demonstration on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')))
    await expect(
      apiSource('/api/v1', 'patient', () => undefined, vi.fn()).list({}, ''),
    ).rejects.toMatchObject({ status: 0 })
  })
  it('refuses authenticated base URLs and plaintext remote APIs', () => {
    expect(() => createHttp('http://remote.invalid/api', () => undefined, vi.fn())).toThrow()
    const syntheticUserInfo = ['user', 'synthetic'].join(':')
    expect(() =>
      createHttp(`https://${syntheticUserInfo}@remote.invalid/api`, () => undefined, vi.fn()),
    ).toThrow()
  })
})
