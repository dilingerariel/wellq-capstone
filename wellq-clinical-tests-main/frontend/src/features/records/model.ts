import { z } from 'zod'
import { createHttp, ApiError } from '../../services/http'
import type { LabReportExportRequest } from '../../types/api.generated'

const number = z.number().finite()
const text = z.string().max(10000)
const nullable = text.nullable().optional()
export const referenceSchema = z.object({
  low: number.nullable().optional(),
  high: number.nullable().optional(),
  unit: nullable,
  source: nullable,
})
export const pointSchema = z.object({
  measured_on: text,
  value: number.nullable(),
  unit: text.nullable(),
  reference: referenceSchema.nullable(),
  status: text.nullable(),
  subscore: number.nullable(),
  subscore_blank_reason: nullable,
  clinical_test_id: text,
  confirmation_level: text.nullable(),
  edited: z.boolean(),
})
export const seriesSchema = z.object({
  patient_id: text,
  from: text.nullable(),
  to: text.nullable(),
  only_confirmed: z.boolean(),
  series: z.array(
    z.object({ marker_code: text, unit: text.nullable(), points: z.array(pointSchema) }),
  ),
})
const pillarSchema = z.object({
  score: number.nullable(),
  coverage: number.min(0).max(1),
  confidence: text,
  status: text.optional(),
})
const scoreSchema = z.object({
  snapshot_id: text,
  patient_id: text.optional(),
  computed_at: text,
  scoring_version: text,
  catalog_version: text,
  lab_index: number.nullable(),
  pillars: z.record(z.string(), pillarSchema),
})
const snapshotSchema = scoreSchema.extend({ catalog_clinically_approved: z.boolean() })
export const scoresSchema = z.object({
  current_snapshot: snapshotSchema,
  history: z.array(snapshotSchema).nullable().optional(),
})
const examSchema = z.object({
  clinical_test_id: text,
  title: nullable,
  test_date: nullable,
  validation_status: nullable,
  review_status: nullable,
})
export const reportSchema = z.object({
  longitudinal: z
    .object({
      marker_series: z.array(
        z.object({
          marker_code: text,
          unit: nullable,
          reference: referenceSchema.nullable(),
          points: z.array(
            z.object({
              measured_on: nullable,
              value: number.nullable(),
              status: nullable,
              clinical_test_id: text,
            }),
          ),
        }),
      ),
      pillar_series: z.array(
        z.object({
          computed_at: text,
          trigger: text,
          scoring_version: text,
          lab_index: number.nullable(),
          pillars: z.record(z.string(), z.object({ score: number.nullable(), coverage: number })),
        }),
      ),
      scoring_version_changes: z.array(z.object({ at: text, from: text, to: text })),
    })
    .nullable(),
  imaging_findings: z.array(z.object({ clinical_test_id: text, findings: z.json().nullable() })),
  generated_at: text,
  header: z.object({
    patient_id: text,
    mode: z.enum(['exam', 'aggregate']),
    window: z.object({ months: number, from: text, to: text }),
    exam: examSchema.nullable(),
    exams: z.array(examSchema),
  }),
  score: scoreSchema.nullable(),
  flags: z.array(
    z.object({
      code: text,
      severity: text,
      marker_code: text.optional(),
      message: text.optional(),
    }),
  ),
  results: z.object({
    panels: z.array(
      z.object({
        panel_code: text.nullable(),
        specimen: nullable,
        rows: z.array(
          z.object({
            marker_code: text,
            name: text,
            value: number.nullable(),
            unit: text.nullable(),
            censoring: nullable,
            edited: z.boolean(),
            reference: referenceSchema,
            status: text,
            subscore: number.nullable(),
            subscore_blank_reason: nullable,
            origin: z.object({ clinical_test_id: text, measured_on: text.nullable() }),
            original: z.object({
              value_raw: nullable,
              unit_raw: nullable,
              conversion_factor: number.nullable().optional(),
            }),
          }),
        ),
      }),
    ),
  }),
  traceability: z.object({
    extractions: z
      .array(z.object({ clinical_test_id: text, extraction_id: nullable, status: nullable }))
      .optional(),
    scoring_version: nullable,
    catalog_version: nullable,
    excluded_markers: z.array(
      z.object({ marker_code: nullable, raw_name: nullable, reason: text }),
    ),
  }),
})
export const exportSchema = z
  .object({
    export_id: text,
    patient_id: text,
    status: z.enum(['ready', 'download_pending']),
    file_name: text,
    download_url: text.nullable(),
    expires_at: text.nullable(),
    size_bytes: z
      .number()
      .int()
      .positive()
      .max(50 * 1024 * 1024),
    sha256: z.string().regex(/^[a-f0-9]{64}$/),
    storage: z.literal('gcs'),
    replayed: z.boolean(),
    generated_at: text,
    error_code: nullable,
  })
  .superRefine((v, c) => {
    if (v.status === 'ready' && (!v.download_url || !v.expires_at))
      c.addIssue({ code: 'custom', message: 'Invalid ready response' })
    if (v.status === 'download_pending' && (v.download_url || v.expires_at))
      c.addIssue({ code: 'custom', message: 'Invalid pending response' })
  })
export type Report = z.infer<typeof reportSchema>
export type Point = z.infer<typeof pointSchema>
export type Scores = z.infer<typeof scoresSchema>
export type ExportResult = z.infer<typeof exportSchema>
export function authorizedReportScore(report: Report, scores?: Scores) {
  const current = scores?.current_snapshot
  return current?.catalog_clinically_approved &&
    current.snapshot_id === report.score?.snapshot_id &&
    current.lab_index === report.score.lab_index
    ? report.score.lab_index
    : null
}
export type ReportParams = Required<
  Pick<LabReportExportRequest, 'window_months' | 'include_series'>
> &
  Pick<LabReportExportRequest, 'clinical_test_id'>
export const reportParams: ReportParams = { window_months: 12, include_series: true }
export function fingerprint(report: Report) {
  const { generated_at: _generated, ...data } = report
  void _generated
  const canonical = (v: unknown): unknown =>
    Array.isArray(v)
      ? v.map(canonical)
      : v && typeof v === 'object'
        ? Object.fromEntries(
            Object.entries(v)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([k, x]) => [k, canonical(x)]),
          )
        : v
  return JSON.stringify(canonical(data))
}
export function reportingApi(http: ReturnType<typeof createHttp>) {
  const path = (id: string) => `/patients/${encodeURIComponent(id)}`
  return {
    report: async (id: string, params: ReportParams, signal?: AbortSignal) => {
      const q = new URLSearchParams({
        window_months: String(params.window_months),
        include_series: String(params.include_series),
        include_snapshot: 'true',
      })
      if (params.clinical_test_id) q.set('clinical_test_id', params.clinical_test_id)
      const result = await http(`${path(id)}/lab-report?${q}`, reportSchema, signal)
      if (result.header.patient_id !== id) throw new ApiError(403, 'RECORD_PATIENT_MISMATCH')
      return result
    },
    markers: async (id: string, code: string, from: string, to: string, signal: AbortSignal) => {
      const q = new URLSearchParams({ marker_codes: code, only_confirmed: 'true' })
      if (from) q.set('from', from)
      if (to) q.set('to', to)
      const result = await http(`${path(id)}/markers?${q}`, seriesSchema, signal)
      if (result.patient_id !== id || result.series.some((s) => s.marker_code !== code))
        throw new ApiError(403, 'RECORD_PATIENT_MISMATCH')
      return result
    },
    scores: async (id: string, signal: AbortSignal) => {
      const result = await http(`${path(id)}/lab-score?history=true`, scoresSchema, signal)
      if ([result.current_snapshot, ...(result.history || [])].some((s) => s.patient_id !== id))
        throw new ApiError(403, 'RECORD_PATIENT_MISMATCH')
      return result
    },
    export: (id: string, body: ReportParams, key: string, signal: AbortSignal) =>
      http(`${path(id)}/lab-report/export`, exportSchema, signal, { body, key }),
  }
}
export type ReportingApi = ReturnType<typeof reportingApi>
export function validDownload(result: ExportResult, now = Date.now()) {
  if (
    result.status !== 'ready' ||
    !result.download_url ||
    !result.expires_at ||
    !Number.isFinite(Date.parse(result.expires_at)) ||
    Date.parse(result.expires_at) <= now
  )
    throw new ApiError(403, 'DOWNLOAD_EXPIRED')
  const url = new URL(result.download_url)
  if (
    url.username ||
    url.password ||
    url.hash ||
    (url.protocol !== 'https:' &&
      !(url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)))
  )
    throw new ApiError(502, 'INVALID_RESPONSE')
  return url.href
}
export async function readPdf(result: ExportResult, signal: AbortSignal) {
  const url = validDownload(result)
  const combined = AbortSignal.any([signal, AbortSignal.timeout(30000)])
  // Separate anonymous transport: backend bearer never accompanies a signed URL.
  const response = await fetch(url, {
    signal: combined,
    credentials: 'omit',
    cache: 'no-store',
    redirect: 'error',
    referrerPolicy: 'no-referrer',
    headers: { Accept: 'application/pdf' },
  })
  if (!response.ok)
    throw new ApiError(
      response.status,
      response.status === 403 ? 'DOWNLOAD_EXPIRED' : 'DOWNLOAD_FAILED',
    )
  const reader = response.body?.getReader()
  if (!reader) throw new ApiError(502, 'DOWNLOAD_FAILED')
  const chunks: Uint8Array[] = []
  let length = 0
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      length += value.length
      if (length > result.size_bytes || length > 50 * 1024 * 1024)
        throw new ApiError(502, 'DOWNLOAD_FAILED')
      chunks.push(value)
    }
  } finally {
    await reader.cancel()
    reader.releaseLock()
  }
  const bytes = new Uint8Array(length)
  let offset = 0
  for (const chunk of chunks) {
    bytes.set(chunk, offset)
    offset += chunk.length
  }
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (x) =>
    x.toString(16).padStart(2, '0'),
  ).join('')
  if (
    length !== result.size_bytes ||
    digest !== result.sha256 ||
    new TextDecoder().decode(bytes.slice(0, 5)) !== '%PDF-'
  )
    throw new ApiError(502, 'DOWNLOAD_FAILED')
  combined.throwIfAborted()
  return bytes
}
export function savePdf(bytes: Uint8Array, name: string) {
  const url = URL.createObjectURL(new Blob([new Uint8Array(bytes)], { type: 'application/pdf' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name.replace(/[\\/:*?"<>|]/g, '_')
  a.rel = 'noopener noreferrer'
  a.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
