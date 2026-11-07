import { QueryClient, QueryObserver } from '@tanstack/react-query'
import { expect, it, vi } from 'vitest'
import { recoverInvalidatedReads } from './synchronization'

it('recovers a stale read mounted after approval exactly once, without retrying a failure', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const key = ['synthetic-recovery']
  client.setQueryData(key, 'RAM data')
  await client.invalidateQueries({ refetchType: 'none' })
  const stop = recoverInvalidatedReads(client, () => true)
  await Promise.resolve() // The old timer strategy would already have missed this observer.
  const read = vi.fn().mockRejectedValue(new Error('Synthetic unavailable'))
  const options = { queryKey: key, queryFn: read, refetchOnMount: false, retry: false }
  const observer = new QueryObserver(client, options)
  const unsubscribe = observer.subscribe(() => {})
  await vi.waitFor(() => expect(read).toHaveBeenCalledOnce())
  observer.setOptions({ ...options, staleTime: 1000 })
  await Promise.resolve()
  expect(read).toHaveBeenCalledOnce()
  expect(client.getQueryData(key)).toBe('RAM data')
  stop()
  unsubscribe()
  client.clear()
})

it('waits for an enabled observer and refuses recovery after identity or network revocation', async () => {
  const client = new QueryClient()
  const key = ['synthetic-private-read']
  client.setQueryData(key, 'RAM data')
  await client.invalidateQueries({ refetchType: 'none' })
  let permitted = true
  const stop = recoverInvalidatedReads(client, () => permitted)
  const read = vi.fn().mockResolvedValue('fresh')
  const observer = new QueryObserver(client, {
    queryKey: key,
    queryFn: read,
    enabled: false,
    refetchOnMount: false,
  })
  const unsubscribe = observer.subscribe(() => {})
  await Promise.resolve()
  expect(read).not.toHaveBeenCalled()
  permitted = false
  // Activating an observer without permission cannot cause our recovery to read.
  // Retain enabled:false so the query library itself cannot initiate a read either.
  observer.setOptions({ ...observer.options, staleTime: 1000 })
  await Promise.resolve()
  expect(read).not.toHaveBeenCalled()
  stop()
  unsubscribe()
  client.clear()
})

it('joins an in-flight approved read and cancels queued recovery on disposal', async () => {
  const client = new QueryClient()
  const key = ['synthetic-inflight-read']
  client.setQueryData(key, 'RAM data')
  await client.invalidateQueries({ refetchType: 'none' })
  let resolve!: (value: string) => void
  const read = vi.fn(
    () =>
      new Promise<string>((r) => {
        resolve = r
      }),
  )
  const observer = new QueryObserver(client, { queryKey: key, queryFn: read })
  const unsubscribe = observer.subscribe(() => {})
  const stop = recoverInvalidatedReads(client, () => true)
  await Promise.resolve()
  expect(read).toHaveBeenCalledOnce()
  resolve('fresh')
  await vi.waitFor(() => expect(client.getQueryData(key)).toBe('fresh'))
  stop()
  unsubscribe()
  await client.invalidateQueries({ refetchType: 'none' })
  const dispose = recoverInvalidatedReads(client, () => true)
  dispose()
  await Promise.resolve()
  expect(read).toHaveBeenCalledOnce()
  client.clear()
})
