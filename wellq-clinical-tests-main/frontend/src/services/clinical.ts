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
  }
}
