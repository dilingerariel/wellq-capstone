import { z } from 'zod'
import { testTypes } from '../../types/clinical'
import type { InitiateUploadRequest } from '../../types/api.generated'
export const uploadMetadata = z.object({
  title: z.string().trim().min(1).max(200),
  test_type: z.enum(testTypes),
  test_date: z.iso.date(),
  ai_consent: z.boolean(),
  notes: z.string().max(2000).optional(),
})
export interface UploadOperationKeys {
  clientUploadId: string
  initiateKey: string
  completeKey: string
}
export function createUploadKeys(): UploadOperationKeys {
  return {
    clientUploadId: crypto.randomUUID(),
    initiateKey: crypto.randomUUID(),
    completeKey: crypto.randomUUID(),
  }
}
/** Local preparation only. No network call, durable storage, progress or clinical mutation. */
export async function prepareUploadIntent(
  file: File,
  metadata: z.infer<typeof uploadMetadata>,
  keys: UploadOperationKeys,
  signal: AbortSignal,
) {
  signal.throwIfAborted()
  const validated = uploadMetadata.parse(metadata)
  if (
    !file.size ||
    file.name.length > 255 ||
    !['application/pdf', 'image/jpeg', 'image/png', 'image/heic'].includes(file.type)
  )
    throw new Error('Unsupported document')
  if (Object.values(keys).some((value) => value.length < 8 || value.length > 200))
    throw new Error('Invalid operation keys')
  const bytes = await file.arrayBuffer()
  signal.throwIfAborted()
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  signal.throwIfAborted()
  const body: InitiateUploadRequest = {
    ...validated,
    client_upload_id: keys.clientUploadId,
    file_name: file.name,
    mime_type: file.type,
    size_bytes: file.size,
    sha256: Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join(
      '',
    ),
  }
  return { body, keys }
}
