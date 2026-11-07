import { afterEach, describe, expect, it, vi } from 'vitest'
import { SessionManager } from './session'
import { Connectivity } from './connectivity'
import { ReadRecovery, allowAutomaticReplay, planReadRetry } from './synchronization'
import { createHttp } from './http'
import { z } from 'zod'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})
const session = (overrides = {}) => ({
  accessToken: 'synthetic-identity-token',
  role: 'patient',
  tenantId: 'synthetic-tenant',
  resourceId: 'synthetic-patient',
  permissions: ['clinical:read'],
  capabilities: [],
  expiresAt: Math.floor(Date.now() / 1000) + 300,
  ...overrides,
})
describe('external identity boundary', () => {
  it('retries provider exceptions and never restores a delayed sign-in after logout', async () => {
    const read = vi
      .fn()
      .mockImplementationOnce(() => {
        throw new Error('synthetic provider failure')
      })
      .mockResolvedValue(session())
    const manager = new SessionManager(() => ({ getSession: read }), vi.fn())
    expect(await manager.verify()).toBe(false)
    expect(await manager.verify()).toBe(true)
    let finish!: () => void
    const signIn = () =>
      new Promise<void>((resolve) => {
        finish = resolve
      })
    const pending = new SessionManager(
      () => ({ getSession: async () => session(), signIn }),
      vi.fn(),
    )
    const signingIn = pending.signIn()
    await pending.signOut()
    finish()
    expect(await signingIn).toBe(false)
    expect(pending.getSnapshot().session).toBeNull()
  })
  it('blocks missing providers and supports authorized sign-in, renewal and logout', async () => {
    const blocked = new SessionManager(() => undefined, vi.fn())
    expect(await blocked.verify()).toBe(false)
    expect(blocked.getSnapshot().phase).toBe('unavailable')
    const signIn = vi.fn().mockResolvedValue(undefined),
      signOut = vi.fn().mockResolvedValue(undefined)
    const provider = {
      getSession: vi.fn().mockResolvedValue(session()),
      signIn,
      signOut,
      refreshSession: vi
        .fn()
        .mockResolvedValue(session({ accessToken: 'synthetic-renewed-token' })),
    }
    const clear = vi.fn()
    const manager = new SessionManager(() => provider, clear)
    expect(await manager.signIn()).toBe(true)
    expect(signIn).toHaveBeenCalledOnce()
    clear.mockClear()
    await manager.verify(true)
    expect(manager.getSnapshot().session?.accessToken).toBe('synthetic-renewed-token')
    expect(clear).not.toHaveBeenCalled()
    await manager.signOut()
    expect(signOut).toHaveBeenCalledOnce()
    expect(clear).toHaveBeenCalledOnce()
    expect(manager.getSnapshot().session).toBeNull()
    expect(await manager.verify()).toBe(false)
  })
  it('deduplicates concurrent renewals, rejects obsolete results and ignores foreign 401 callbacks', async () => {
    let resolve!: (value: unknown) => void
    const getSession = vi.fn(
      () =>
        new Promise((resolve_) => {
          resolve = resolve_
        }),
    )
    const manager = new SessionManager(() => ({ getSession }), vi.fn())
    const first = manager.verify(),
      second = manager.verify()
    expect(first).toBe(second)
    expect(getSession).toHaveBeenCalledOnce()
    await manager.signOut()
    resolve(session())
    await first
    expect(manager.getSnapshot().session).toBeNull()
    const current = new SessionManager(() => ({ getSession: async () => session() }), vi.fn())
    await current.verify()
    current.invalidate('synthetic-obsolete-token')
    expect(current.getSnapshot().phase).toBe('authenticated')
  })
  it('clears private queries on grant, tenant and patient changes and closes on invalid sessions', async () => {
    const provider = { getSession: vi.fn().mockResolvedValue(session()) }
    const clear = vi.fn()
    const manager = new SessionManager(() => provider, clear)
    await manager.verify()
    clear.mockClear()
    provider.getSession.mockResolvedValue(
      session({ tenantId: 'different-synthetic-tenant', permissions: [] }),
    )
    await manager.verify()
    expect(clear).toHaveBeenCalledOnce()
    provider.getSession.mockResolvedValue(session({ expiresAt: 1 }))
    await manager.verify()
    expect(manager.getSnapshot().phase).toBe('expired')
    expect(manager.getSnapshot().session).toBeNull()
  })
})
describe('connectivity evidence and timeout', () => {
  it('accepts a healthy probe even when navigator reports offline', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('{"status":"ok"}', { status: 200 })),
    )
    const network = new Connectivity('/health')
    await network.check()
    expect(network.getSnapshot().status).toBe('online')
  })
  it('distinguishes unreachable service, HTTP failure and recovery', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
    const fetch = vi.fn().mockRejectedValue(new TypeError('synthetic outage'))
    vi.stubGlobal('fetch', fetch)
    const network = new Connectivity('/health')
    await network.check()
    expect(network.getSnapshot().status).toBe('unreachable')
    fetch.mockResolvedValue(new Response('{}', { status: 503 }))
    await network.check()
    expect(network.getSnapshot().status).toBe('unavailable')
    fetch.mockResolvedValue(new Response('{"status":"ok"}'))
    await network.check()
    expect(network.getSnapshot()).toMatchObject({ status: 'online', recovery: 1 })
  })
  it('aborts timed-out requests and preserves deliberate caller cancellation', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url, init: RequestInit) =>
          new Promise((_resolve, reject) =>
            init.signal?.addEventListener('abort', () =>
              reject(new DOMException('Aborted', 'AbortError')),
            ),
          ),
      ),
    )
    const report = vi.fn()
    const http = createHttp('/api/v1', () => undefined, vi.fn(), report, 10)
    await expect(http('/clinical-tests', z.unknown())).rejects.toMatchObject({
      status: 0,
      code: 'REQUEST_TIMEOUT',
    })
    expect(report).toHaveBeenCalledWith('timeout')
    const controller = new AbortController()
    const cancelled = http('/clinical-tests', z.unknown(), controller.signal)
    controller.abort()
    await expect(cancelled).rejects.toMatchObject({ name: 'AbortError' })
  })
})
describe('read-only recovery policy', () => {
  it('bounds future read backoff, honors Retry-After and rejects expired grants/conflicts', () => {
    const operation = {
      operationId: 'synthetic-read',
      idempotencyKey: 'synthetic-key',
      kind: 'read' as const,
      requiredPermission: 'clinical:read',
      signal: new AbortController().signal,
    }
    expect(planReadRetry(operation, 0, 503, ['clinical:read'], 0, () => 0)).toBe(1000)
    expect(planReadRetry(operation, 1, 429, ['clinical:read'], 5000, () => 0)).toBe(5000)
    expect(planReadRetry(operation, 3, 503, ['clinical:read'])).toBeNull()
    expect(planReadRetry(operation, 0, 409, ['clinical:read'])).toBeNull()
    expect(planReadRetry(operation, 0, 503, [])).toBeNull()
  })
  it('deduplicates read recoveries and refuses automatic clinical mutation replay', async () => {
    const recovery = new ReadRecovery()
    const read = vi.fn().mockResolvedValue(undefined)
    await Promise.all([recovery.run('same-operation', read), recovery.run('same-operation', read)])
    expect(read).toHaveBeenCalledOnce()
    expect(() =>
      allowAutomaticReplay({
        operationId: 'synthetic-operation',
        idempotencyKey: 'synthetic-key',
        kind: 'clinical-mutation',
        requiredPermission: 'clinical:write',
        signal: new AbortController().signal,
      }),
    ).toThrow('approved durable storage')
  })
})
