import { sessionSchema, type IdentityProvider, type PortalSession } from '../types/session'

export type SessionPhase =
  'loading' | 'authenticated' | 'signed-out' | 'unavailable' | 'expired' | 'error'
export interface SessionState {
  session: PortalSession | null
  phase: SessionPhase
  boundary: number
}
export function principal(session: PortalSession | null) {
  return session
    ? JSON.stringify([
        session.tenantId,
        session.resourceId,
        session.role,
        [...session.permissions].sort(),
        [...session.capabilities].sort(),
      ])
    : ''
}
/** In-memory identity boundary. Does not issue tokens, redirect URLs or persist credentials. */
export class SessionManager {
  private state: SessionState = { session: null, phase: 'loading', boundary: 0 }
  private listeners = new Set<() => void>()
  private generation = 0
  private locked = false
  private flight: Promise<boolean> | null = null
  constructor(
    private provider: () => IdentityProvider | undefined,
    private clearPrivateState: () => void,
  ) {}
  getSnapshot = () => this.state
  subscribe = (callback: () => void) => {
    this.listeners.add(callback)
    return () => {
      this.listeners.delete(callback)
    }
  }
  private commit(session: PortalSession | null, phase: SessionPhase) {
    const changed = principal(session) !== principal(this.state.session)
    if (changed) this.clearPrivateState()
    this.state = { session, phase, boundary: this.state.boundary + Number(changed) }
    this.listeners.forEach((callback) => callback())
  }
  invalidate = (expectedToken?: string, phase: SessionPhase = 'signed-out') => {
    if (expectedToken && expectedToken !== this.state.session?.accessToken) return
    this.generation++
    this.flight = null
    this.locked = true
    this.commit(null, phase)
  }
  verify = (refresh = false, explicit = false): Promise<boolean> => {
    if (this.locked && !explicit) return Promise.resolve(false)
    if (explicit) this.locked = false
    if (this.flight) return this.flight
    const provider = this.provider()
    if (!provider) {
      this.commit(null, 'unavailable')
      return Promise.resolve(false)
    }
    const generation = ++this.generation
    this.commit(this.state.session, 'loading')
    const operation = (async () => {
      try {
        const value = await (refresh && provider.refreshSession
          ? provider.refreshSession()
          : provider.getSession())
        if (generation !== this.generation) return false
        const result = sessionSchema.safeParse(value)
        if (!result.success || result.data.expiresAt * 1000 <= Date.now()) {
          this.commit(null, result.success ? 'expired' : 'signed-out')
          return false
        }
        this.commit(result.data, 'authenticated')
        return true
      } catch {
        if (generation === this.generation) this.commit(null, 'error')
        return false
      }
    })()
    this.flight = operation.finally(() => {
      if (generation === this.generation) this.flight = null
    })
    return this.flight
  }
  async signIn() {
    const provider = this.provider()
    if (!provider?.signIn) return false
    const generation = ++this.generation
    this.flight = null
    this.commit(null, 'loading')
    try {
      await provider.signIn()
      if (generation !== this.generation) return false
      return this.verify(false, true)
    } catch {
      if (generation === this.generation) this.commit(null, 'error')
      return false
    }
  }
  async signOut() {
    this.invalidate()
    const generation = this.generation
    try {
      await this.provider()?.signOut?.()
    } catch {
      if (generation === this.generation) this.commit(null, 'error')
    }
  }
  connect() {
    void this.verify()
    const unsubscribe = this.provider()?.subscribe?.(() => {
      if (this.locked) return
      // A change notification revokes the old view before reading the new identity.
      this.generation++
      this.flight = null
      this.commit(null, 'loading')
      void this.verify()
    })
    return () => {
      this.generation++
      this.flight = null
      unsubscribe?.()
    }
  }
}
