import { z } from 'zod'
import { extractionStates } from '../uploads/api'
import { examSchema } from '../../types/clinical'
import type { PatientConfirmationRequest } from '../../types/api.generated'
import { createHttp } from '../../services/http'

export const documentTypes = [
  'blood_panel',
  'urine_panel',
  'imaging_report',
  'other',
  'unreadable',
] as const
const reference = z.object({
  low: z.number().nullable().optional(),
  high: z.number().nullable().optional(),
  unit: z.string().nullable().optional(),
  source: z.string().optional(),
  text_raw: z.string().nullable().optional(),
})
export const extractionSchema = z.object({
  clinical_test_id: z.string().min(1),
  extraction_id: z.string().min(1),
  status: z.enum(extractionStates),
  document: z.object({
    document_type: z.enum(documentTypes).default('blood_panel'),
    description: z.string().default(''),
    collection_date: z.string().nullable().optional(),
    report_date: z.string().nullable().optional(),
  }),
  panels: z
    .array(
      z.object({
        panel_code: z.string(),
        panel_name_raw: z.string(),
        specimen: z.string().optional(),
        collection_date: z.string().nullable().optional(),
        markers: z.array(
          z.object({
            marker_code: z.string(),
            raw_name: z.string(),
            value_raw: z.string(),
            unit_raw: z.string(),
            value_type: z.string().default('numeric'),
            mapping_status: z.string().default('mapped'),
            reference: reference.nullable().optional(),
            confidence: z.record(z.string(), z.number()).optional(),
            provenance: z.record(z.string(), z.unknown()).optional(),
            validation: z.record(z.string(), z.unknown()).optional(),
          }),
        ),
      }),
    )
    .default([]),
  flags: z.array(z.record(z.string(), z.unknown())).default([]),
})
export type Extraction = z.infer<typeof extractionSchema>
export type Marker = Extraction['panels'][number]['markers'][number]
export interface Draft {
  collection_date: string
  report_date: string
  document_type: Extraction['document']['document_type']
  markers: Record<string, { value: string; unit: string }>
  acknowledged: string[]
  identity: boolean
}
export function draftFor(ext: Extraction): Draft {
  return {
    collection_date: ext.document.collection_date || '',
    report_date: ext.document.report_date || '',
    document_type: ext.document.document_type,
    markers: Object.fromEntries(
      ext.panels.flatMap((p) =>
        p.markers.map((m) => [m.marker_code, { value: m.value_raw, unit: m.unit_raw }]),
      ),
    ),
    acknowledged: [],
    identity: false,
  }
}
export const markersOf = (ext: Extraction) => ext.panels.flatMap((p) => p.markers)
export const identityRequired = (ext: Extraction) =>
  ext.flags.some((f) => ['identity_unverified', 'identity_mismatch'].includes(String(f.code)))
export const lowCodes = (ext: Extraction) => [
  ...new Set(
    ext.flags.filter((f) => f.code === 'low_confidence').map((f) => String(f.marker_code || '')),
  ),
]
export function editable(ext: Extraction, m: Marker) {
  return (
    m.mapping_status === 'mapped' &&
    m.value_type === 'numeric' &&
    markersOf(ext).filter((x) => x.marker_code === m.marker_code).length === 1
  )
}
export function payloadFor(ext: Extraction, draft: Draft): PatientConfirmationRequest {
  const codes = markersOf(ext).map((m) => m.marker_code)
  if (new Set(codes).size !== codes.length) throw new Error('reviewDuplicate')
  const edits: NonNullable<PatientConfirmationRequest['document_edits']> = {}
  for (const field of ['collection_date', 'report_date'] as const) {
    if (draft[field] !== (ext.document[field] || '')) {
      if (
        !/^\d{4}-\d{2}-\d{2}$/.test(draft[field]) ||
        Number.isNaN(Date.parse(draft[field])) ||
        new Date(draft[field]).toISOString().slice(0, 10) !== draft[field] ||
        draft[field] > new Date().toISOString().slice(0, 10)
      )
        throw new Error('reviewInvalid')
      edits[field] = draft[field]
    }
  }
  if (draft.document_type !== ext.document.document_type) edits.document_type = draft.document_type
  if (identityRequired(ext)) {
    if (!draft.identity) throw new Error('reviewAcknowledgments')
    edits.identity_confirmed = true
  }
  if (!lowCodes(ext).every((code) => draft.acknowledged.includes(code)))
    throw new Error('reviewAcknowledgments')
  const marker_edits: NonNullable<PatientConfirmationRequest['marker_edits']> = []
  for (const m of markersOf(ext)) {
    const d = draft.markers[m.marker_code]
    if (d && (d.value !== m.value_raw || d.unit !== m.unit_raw)) {
      if (
        !editable(ext, m) ||
        !d.value.trim() ||
        !d.unit.trim() ||
        d.value.length > 200 ||
        d.unit.length > 100
      )
        throw new Error('reviewInvalid')
      marker_edits.push({
        op: 'update',
        marker_code: m.marker_code,
        value_raw: d.value,
        unit_raw: d.unit,
        ...(m.reference ? { reference: m.reference } : {}),
      })
    }
  }
  return {
    action: 'confirm',
    extraction_id: ext.extraction_id,
    document_edits: edits,
    marker_edits,
    acknowledged_marker_codes: [...draft.acknowledged].sort(),
  }
}
export function reviewApi(http: ReturnType<typeof createHttp>) {
  const path = (id: string) => `/clinical-tests/${encodeURIComponent(id)}`
  return {
    document: (id: string, signal: AbortSignal) => http(path(id), examSchema, signal),
    extraction: (id: string, signal: AbortSignal) =>
      http(`${path(id)}/extraction`, extractionSchema, signal),
    confirm: (id: string, body: PatientConfirmationRequest, key: string, signal: AbortSignal) =>
      http(`${path(id)}/extraction`, extractionSchema, signal, { body, key, method: 'PATCH' }),
  }
}
export type ReviewApi = ReturnType<typeof reviewApi>
