import { z } from 'zod'
import { examSchema } from '../../types/clinical'
import { extractionSchema, markersOf, editable, type Extraction } from '../review/model'
import { createHttp } from '../../services/http'
import type { ReviewRequest, ClinicianValidationRequest } from '../../types/api.generated'
export const documentSchema = examSchema.extend({
  review: z.object({
    status: z.enum(['not_reviewed', 'reviewed']),
    reviewed_by: z.string().nullable().optional(),
    reviewed_at: z.string().nullable().optional(),
  }),
})
export type ClinicalDocument = z.infer<typeof documentSchema>
// Deliberately exclude private notes; GET does not provide a private-note read contract.
export const proposalSchema = extractionSchema.extend({
  confirmation: z
    .object({
      validated_by: z.string().nullable().optional(),
      validated_at: z.string().nullable().optional(),
    })
    .default({}),
})
export type ClinicalExtraction = z.infer<typeof proposalSchema>
export type Action = 'review' | 'validated' | 'rejected'
export interface ClinicalDraft {
  reviewNote: string
  clinicalNote: string
  markers: Record<string, { value: string; unit: string; reason: string }>
}
export function createDraft(ext?: Extraction): ClinicalDraft {
  return {
    reviewNote: '',
    clinicalNote: '',
    markers: Object.fromEntries(
      (ext ? markersOf(ext) : []).map((m) => [
        m.marker_code,
        { value: m.value_raw, unit: m.unit_raw, reason: '' },
      ]),
    ),
  }
}
export function bodyFor(
  action: Action,
  d: ClinicalDraft,
  ext?: Extraction,
): ReviewRequest | ClinicianValidationRequest {
  if (action === 'review') {
    if (d.reviewNote.length > 2000) throw new Error('clinicalInvalid')
    return { review_status: 'reviewed', review_note: d.reviewNote || null }
  }
  if (!ext || ext.status !== 'confirmed' || d.clinicalNote.length > 2000)
    throw new Error('clinicalInvalid')
  const all = markersOf(ext)
  if (new Set(all.map((m) => m.marker_code)).size !== all.length) throw new Error('reviewDuplicate')
  const corrections: NonNullable<ClinicianValidationRequest['marker_corrections']> = []
  for (const m of all) {
    const edit = d.markers[m.marker_code]
    if (edit && (edit.value !== m.value_raw || edit.unit !== m.unit_raw)) {
      if (
        !editable(ext, m) ||
        m.validation?.passed === false ||
        !edit.value.trim() ||
        !edit.unit.trim() ||
        edit.value.length > 200 ||
        edit.unit.length > 100 ||
        edit.reason.length > 1000
      )
        throw new Error('clinicalInvalid')
      corrections.push({
        marker_code: m.marker_code,
        value_raw: edit.value,
        unit_raw: edit.unit,
        reason: edit.reason || 'clinical_correction',
      })
    }
  }
  // The rejection branch of the server ignores corrections. Never silently discard them.
  if (action === 'rejected' && corrections.length) throw new Error('clinicalRejectEdits')
  return {
    validation_status: action,
    clinical_note: d.clinicalNote || null,
    marker_corrections: corrections,
  }
}
export function clinicianApi(http: ReturnType<typeof createHttp>) {
  const path = (id: string) => `/clinical-tests/${encodeURIComponent(id)}`
  return {
    document: (id: string, s: AbortSignal) => http(path(id), documentSchema, s),
    extraction: (id: string, s: AbortSignal) => http(`${path(id)}/extraction`, proposalSchema, s),
    review: (id: string, body: ReviewRequest, s: AbortSignal) =>
      http(`${path(id)}/review`, documentSchema, s, { body, method: 'PATCH' }),
    validate: (id: string, body: ClinicianValidationRequest, s: AbortSignal) =>
      http(`${path(id)}/extraction/validate`, proposalSchema, s, { body, method: 'POST' }),
  }
}
export type ClinicianApi = ReturnType<typeof clinicianApi>
