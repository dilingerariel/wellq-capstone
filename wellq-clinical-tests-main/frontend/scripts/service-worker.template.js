/* Only public build assets. No runtime caching of medical URLs, tokens or documents. */
const CACHE_NAME = __CACHE_NAME__
const PUBLIC_ASSETS = __PUBLIC_ASSETS__
const STATIC = new Set(PUBLIC_ASSETS)
self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME)
      for (const path of PUBLIC_ASSETS) {
        const response = await fetch(
          new Request(path, { cache: 'reload', credentials: 'omit', redirect: 'error' }),
        )
        if (!response.ok) throw new Error('Shell installation incomplete')
        await cache.put(path, response)
      }
    })(),
  )
})
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      for (const name of await caches.keys())
        if (name.startsWith('wellq-shell-') && name !== CACHE_NAME) await caches.delete(name)
      await self.clients.claim()
    })(),
  )
})
self.addEventListener('message', (event) => {
  if (event.data?.type === 'APPLY_UPDATE') void self.skipWaiting()
})
self.addEventListener('fetch', (event) => {
  const request = event.request
  const url = new URL(request.url)
  if (
    request.method !== 'GET' ||
    url.origin !== self.location.origin ||
    request.headers.has('Authorization') ||
    url.search
  )
    return
  const shellRoute =
    request.mode === 'navigate' &&
    /^\/(?:|clinical|patient|exams(?:\/[^/]+)?|catalog|dashboard\/?|demo)$/.test(url.pathname)
  if (!shellRoute && !STATIC.has(url.pathname)) return
  event.respondWith(
    (async () => {
      const cached = await (
        await caches.open(CACHE_NAME)
      ).match(shellRoute ? '/index.html' : url.pathname)
      return cached || fetch(request)
    })(),
  )
})
