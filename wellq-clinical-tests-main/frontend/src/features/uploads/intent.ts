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
export type UploadMetadata = z.infer<typeof uploadMetadata>
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024
const mimeByExtension: Record<string, string> = {
  pdf: 'application/pdf',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  heic: 'image/heic',
}
export function validateUploadFile(file: File) {
  const name = file.name.normalize('NFC')
  const parts = name.toLowerCase().split('.')
  const mime = mimeByExtension[parts.at(-1) || '']
  if (
    !name ||
    name.length > 255 ||
    /[/\\:<>"|?*\p{Cc}\u202a-\u202e\u2066-\u2069]/u.test(name) ||
    /[. ]$/.test(name) ||
    !parts.slice(0, -1).some(Boolean) ||
    parts
      .slice(1, -1)
      .some((p) =>
        ['exe', 'com', 'bat', 'cmd', 'ps1', 'vbs', 'js', 'msi', 'scr', 'dll', 'hta', 'sh'].includes(
          p,
        ),
      ) ||
    !mime ||
    (file.type && file.type !== mime)
  )
    throw new Error('uploadInvalidFile')
  if (!file.size || file.size > MAX_UPLOAD_BYTES) throw new Error('uploadInvalidSize')
  return { name, mime }
}
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
  const { name, mime } = validateUploadFile(file)
  if (Object.values(keys).some((value) => value.length < 8 || value.length > 200))
    throw new Error('Invalid operation keys')
  const bytes = await file.arrayBuffer()
  signal.throwIfAborted()
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  signal.throwIfAborted()
  const body: InitiateUploadRequest = {
    ...validated,
    client_upload_id: keys.clientUploadId,
    file_name: name,
    mime_type: mime,
    size_bytes: file.size,
    sha256: Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join(
      '',
    ),
  }
  return { body, keys }
}
