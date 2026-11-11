import { expect, it, vi } from 'vitest'
import { resolveDataMode } from './data-mode'
import { SessionManager } from '../services/session'

it('fails closed in production without identity and preserves development demonstration', async () => {
  expect(resolveDataMode(undefined, true)).toBe('api')
  expect(resolveDataMode('', true)).toBe('api')
  expect(resolveDataMode('api', true)).toBe('api')
  expect(() => resolveDataMode('demo', true)).toThrow('Production requires API mode')
  expect(() => resolveDataMode('unknown', true)).toThrow('VITE_DATA_MODE must be demo or api')
  expect(resolveDataMode(undefined, false)).toBe('demo')
  expect(resolveDataMode('demo', false)).toBe('demo')
  expect(resolveDataMode('api', false)).toBe('api')
  expect(() => resolveDataMode('unknown', false)).toThrow('VITE_DATA_MODE must be demo or api')

  // Actual session manager, no mocked identity or fabricated JWT. No HTTP calls.
  const manager = new SessionManager(() => undefined, vi.fn())
  expect(await manager.verify()).toBe(false)
  expect(await manager.signIn()).toBe(false)
  expect(manager.getSnapshot()).toMatchObject({ phase: 'unavailable', session: null })
})
