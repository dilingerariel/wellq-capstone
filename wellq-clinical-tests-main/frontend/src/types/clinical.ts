import { z } from 'zod'
import type { ClinicalTestResponse, TestType, UploadStatus } from './api.generated'

export const statuses = [
  'initiated',
  'object_uploaded',
  'processing',
  'ready_for_review',
  'rejected',
  'failed',
  'deleted',
] as const satisfies readonly UploadStatus[]
export const testTypes = [
  'blood_test',
  'urine_test',
  'imaging',
  'pathology',
  'other',
] as const satisfies readonly TestType[]
// ListClinicalTestsResponse.items is an open dictionary in OpenAPI. The route serializes
// each item with ClinicalTestResponse; validate the fields actually rendered, at runtime.
export const examSchema = z.object({
  clinical_test_id: z.string(),
  patient_id: z.string(),
  title: z.string(),
  test_type: z.enum(testTypes),
  test_date: z.string(),
  notes: z.string().nullable().optional(),
  file: z.object({
    name: z.string(),
    mime_type: z.string(),
    size_bytes: z.number().int().nonnegative(),
  }),
  status: z.enum(statuses),
  review: z.object({ status: z.enum(['not_reviewed', 'reviewed']) }),
  created_at: z.string(),
  updated_at: z.string(),
})
export type Exam = z.infer<typeof examSchema>
export type DetailContract = ClinicalTestResponse
export const pageSchema = z.object({
  items: z.array(examSchema),
  next_cursor: z.string().nullable().optional(),
})
export type ExamPage = z.infer<typeof pageSchema>
export interface ExamFilters {
  status?: UploadStatus
  test_type?: TestType
  cursor?: string
}
export const catalogSchema = z.array(
  z.object({
    marker_code: z.string(),
    name: z.string(),
    panel_code: z.string(),
    canonical_unit: z.string(),
    clinically_validated: z.boolean().default(false),
    catalog_version: z.string().optional(),
  }),
)
export type Catalog = z.infer<typeof catalogSchema>
