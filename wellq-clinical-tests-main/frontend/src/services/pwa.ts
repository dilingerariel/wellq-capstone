type State = { updateReady: boolean; available: boolean }
let state: State = { updateReady: false, available: false }
const listeners = new Set<() => void>()
let registration: ServiceWorkerRegistration | null = null
let started = false
function publish(next: State) {
  state = next
  listeners.forEach((listener) => listener())
}
export const pwa = {
  getSnapshot: () => state,
  subscribe(callback: () => void) {
    listeners.add(callback)
    return () => {
      listeners.delete(callback)
    }
  },
  async start() {
    if (started || !import.meta.env.PROD || !('serviceWorker' in navigator)) return
    started = true
    try {
      registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        updateViaCache: 'none',
      })
      const check = () =>
        publish({
          updateReady: Boolean(registration?.waiting),
          available: Boolean(navigator.serviceWorker.controller),
        })
      registration.addEventListener('updatefound', () =>
        registration?.installing?.addEventListener('statechange', () =>
          window.setTimeout(check, 0),
        ),
      )
      navigator.serviceWorker.addEventListener('controllerchange', check)
      check()
    } catch {
      publish({ updateReady: false, available: false })
    }
  },
  apply() {
    if (!registration?.waiting) return
    navigator.serviceWorker.addEventListener('controllerchange', () => window.location.reload(), {
      once: true,
    })
    registration.waiting.postMessage({ type: 'APPLY_UPDATE' })
  },
}
