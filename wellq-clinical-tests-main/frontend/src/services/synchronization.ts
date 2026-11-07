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
