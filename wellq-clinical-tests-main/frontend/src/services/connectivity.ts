export type ConnectionStatus =
  'checking' | 'online' | 'offline' | 'unreachable' | 'timeout' | 'unavailable'
export interface ConnectionState {
  status: ConnectionStatus
  recovery: number
}
export class Connectivity {
  private state: ConnectionState = { status: 'checking', recovery: 0 }
  private listeners = new Set<() => void>()
  private flight: Promise<void> | null = null
  private controller: AbortController | null = null
  private generation = 0
  constructor(
    private healthUrl: string | null,
    private timeoutMs = 5000,
  ) {}
  getSnapshot = () => this.state
  subscribe = (callback: () => void) => {
    this.listeners.add(callback)
    return () => {
      this.listeners.delete(callback)
    }
  }
  report = (status: ConnectionStatus) => {
    if (this.state.status === status) return
    const recovered = status === 'online' && !['online', 'checking'].includes(this.state.status)
    this.state = { status, recovery: this.state.recovery + Number(recovered) }
    this.listeners.forEach((callback) => callback())
  }
  check = (): Promise<void> => {
    if (this.flight) return this.flight
    if (!this.healthUrl) {
      this.report(navigator.onLine ? 'online' : 'offline')
      return Promise.resolve()
    }
    this.controller = new AbortController()
    const generation = ++this.generation
    const controller = this.controller
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs)
    this.flight = (async () => {
      try {
        const response = await fetch(this.healthUrl!, {
          signal: controller.signal,
          cache: 'no-store',
          credentials: 'omit',
          redirect: 'error',
          headers: { Accept: 'application/json' },
        })
        const data: unknown = response.ok ? await response.json() : null
        if (generation === this.generation)
          this.report(
            response.ok &&
              typeof data === 'object' &&
              data !== null &&
              'status' in data &&
              data.status === 'ok'
              ? 'online'
              : 'unavailable',
          )
      } catch {
        if (generation === this.generation)
          this.report(
            !navigator.onLine ? 'offline' : controller.signal.aborted ? 'timeout' : 'unreachable',
          )
      } finally {
        window.clearTimeout(timer)
        if (generation === this.generation) this.flight = null
      }
    })()
    return this.flight
  }
  start() {
    const changed = () => {
      // Offline is a browser hint; the probe independently confirms backend availability.
      if (!navigator.onLine) this.report('offline')
      void this.check()
    }
    const visible = () => {
      if (document.visibilityState === 'visible') void this.check()
    }
    changed()
    window.addEventListener('online', changed)
    window.addEventListener('offline', changed)
    document.addEventListener('visibilitychange', visible)
    const timer = window.setInterval(visible, 30_000)
    return () => {
      window.clearInterval(timer)
      this.generation++
      this.controller?.abort()
      this.flight = null
      window.removeEventListener('online', changed)
      window.removeEventListener('offline', changed)
      document.removeEventListener('visibilitychange', visible)
    }
  }
}
