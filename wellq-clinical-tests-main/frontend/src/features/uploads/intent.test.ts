import { describe, expect, it, vi } from 'vitest'
import { webcrypto } from 'node:crypto'
import { createUploadKeys, prepareUploadIntent } from './intent'

const metadata = {
  title: 'Synthetic document',
  test_type: 'blood_test' as const,
  test_date: '2026-01-01',
  ai_consent: false,
}
function file(type = 'application/pdf') {
  return Object.assign(new File(['abc'], 'synthetic.pdf', { type }), {
    arrayBuffer: async () => new TextEncoder().encode('abc').buffer,
  })
}
describe('future signed upload preparation without network or persistence', () => {
  it('hashes actual bytes and preserves operation keys without supplying patient or tenant authority', async () => {
    vi.stubGlobal('crypto', webcrypto)
    try {
      const fetch = vi.spyOn(globalThis, 'fetch')
      const keys = createUploadKeys()
      const intent = await prepareUploadIntent(file(), metadata, keys, new AbortController().signal)
      expect(intent.body.sha256).toBe(
        'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
      )
      expect(intent.keys).toBe(keys)
      expect(intent.body.client_upload_id).toBe(keys.clientUploadId)
      expect(intent.body).not.toHaveProperty('patient_id')
      expect(intent.body).not.toHaveProperty('client_id')
      expect(fetch).not.toHaveBeenCalled()
      fetch.mockRestore()
    } finally {
      vi.unstubAllGlobals()
    }
  })
  it('rejects cancellation and unsupported documents before reading bytes', async () => {
    const keys = {
      clientUploadId: 'synthetic-upload',
      initiateKey: 'synthetic-initiate',
      completeKey: 'synthetic-complete',
    }
    const controller = new AbortController()
    controller.abort()
    await expect(
      prepareUploadIntent(file(), metadata, keys, controller.signal),
    ).rejects.toMatchObject({ name: 'AbortError' })
    await expect(
      prepareUploadIntent(file('text/html'), metadata, keys, new AbortController().signal),
    ).rejects.toThrow('Unsupported document')
  })
})
