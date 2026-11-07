import type { QueryClient } from '@tanstack/react-query'

/** Recover invalidated reads even when an observer mounts after identity approval. */
export function recoverInvalidatedReads(client: QueryClient, permitted: () => boolean) {
  let active = true,
    queued = false
  const attempted = new Set<string>()
  const schedule = () => {
    if (!active || queued) return
    queued = true
    queueMicrotask(() => {
      queued = false
      if (!active || !permitted()) return
      const targets = new Set(
        client
          .getQueryCache()
          .findAll({ type: 'active' })
          .filter((q) => q.state.isInvalidated && !attempted.has(q.queryHash))
          .map((q) => q.queryHash),
      )
      targets.forEach((hash) => attempted.add(hash))
      // Join an existing read, without cancelling it or retrying errors in a loop.
      void client.refetchQueries(
        { type: 'active', predicate: (q) => targets.has(q.queryHash) },
        { cancelRefetch: false },
      )
    })
  }
  const unsubscribe = client.getQueryCache().subscribe((event) => {
    if (event.type === 'observerAdded' || event.type === 'observerOptionsUpdated') schedule()
  })
  schedule()
  return () => {
    active = false
    unsubscribe()
  }
}

/** One concurrent read recovery per key. No persistent queue and no mutation replay. */
export class ReadRecovery {
  private running = new Map<string, Promise<void>>()
  run(key: string, action: () => Promise<void>) {
    const existing = this.running.get(key)
    if (existing) return existing
    const task = Promise.resolve()
      .then(action)
      .finally(() => {
        if (this.running.get(key) === task) this.running.delete(key)
      })
    this.running.set(key, task)
    return task
  }
}
export interface FutureOperation {
  operationId: string
  idempotencyKey: string
  kind: 'read' | 'clinical-mutation'
  expectedVersion?: string
  requiredPermission: string
  signal: AbortSignal
}
export function allowAutomaticReplay(operation: FutureOperation) {
  operation.signal.throwIfAborted()
  if (operation.kind !== 'read')
    throw new Error('Clinical replay requires an approved durable storage and conflict policy')
}

/** Future read retry policy; no timers, persistence or clinical mutation dispatch is enabled. */
export function planReadRetry(
  operation: FutureOperation,
  attempt: number,
  status: number,
  permissions: readonly string[],
  retryAfterMs = 0,
  random = Math.random,
): number | null {
  allowAutomaticReplay(operation)
  if (
    !operation.operationId ||
    !operation.idempotencyKey ||
    !permissions.includes(operation.requiredPermission) ||
    attempt >= 3 ||
    attempt < 0 ||
    ![0, 429, 500, 503].includes(status)
  )
    return null
  return Math.max(retryAfterMs, Math.min(30_000, 1000 * 2 ** attempt + Math.floor(random() * 250)))
}
