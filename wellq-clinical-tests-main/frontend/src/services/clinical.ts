import { z } from 'zod'
import type { Role } from '../types/session'
import {
  catalogSchema,
  examSchema,
  pageSchema,
  type Catalog,
  type Exam,
  type ExamFilters,
  type ExamPage,
} from '../types/clinical'
import { createHttp } from './http'
import type { ConnectionStatus } from './connectivity'

export interface ClinicalSource {
  list: (filters: ExamFilters, patientId: string, signal?: AbortSignal) => Promise<ExamPage>
  detail: (id: string, signal?: AbortSignal) => Promise<Exam>
  catalog: (signal?: AbortSignal) => Promise<Catalog>
  downloadUrl: (id: string, signal?: AbortSignal) => Promise<{ url: string; expires_at: string; file_name: string }>
}
export function apiSource(
  base: string,
  role: Role,
  token: () => string | undefined,
  unauthorized: (token?: string) => void,
  report?: (status: ConnectionStatus) => void,
): ClinicalSource {
  const http = createHttp(base, token, unauthorized, report)
  return {
    list: (filters, patientId, signal) => {
      const params = new URLSearchParams({ limit: '6' })
      for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v)
      const path =
        role === 'clinician'
          ? `/patients/${encodeURIComponent(patientId)}/clinical-tests`
          : '/clinical-tests'
      return http(`${path}?${params}`, pageSchema, signal)
    },
    detail: (id, signal) => http(`/clinical-tests/${encodeURIComponent(id)}`, examSchema, signal),
    catalog: (signal) => http('/marker-catalog', catalogSchema, signal),
    downloadUrl: async (id, signal) => {
      const result = await http(`/clinical-tests/${encodeURIComponent(id)}/download-url`,
        downloadUrlSchema, signal, { method: 'POST', body: {} })
      const url = new URL(result.url, new URL(base, window.location.origin))
      const apiOrigin = new URL(base, window.location.origin).origin
      if (url.username || url.password || url.hash ||
          (url.protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) ||
          (url.origin !== apiOrigin && url.hostname !== 'storage.googleapis.com') ||
          !Number.isFinite(Date.parse(result.expires_at)) || Date.parse(result.expires_at) <= Date.now()) {
        throw new Error('Invalid signed document URL')
      }
      return { ...result, url: url.href }
    },
  }
}

const downloadUrlSchema = z.object({
  url: z.string().min(1).max(4096),
  expires_at: z.string().min(1).max(100),
  file_name: z.string().min(1).max(255),
})
