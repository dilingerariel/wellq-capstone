import type { ClinicalSource } from '../../services/clinical'
import type { Exam } from '../../types/clinical'
import { ApiError } from '../../services/http'

// Invented documents only. Never a fallback after a failed API request. No clinical scores.
const items: Exam[] = [
  [
    '01',
    'Panel de laboratorio · DEMO',
    'blood_test',
    'ready_for_review',
    '2026-10-28',
    'not_reviewed',
  ],
  ['02', 'Control de orina · DEMO', 'urine_test', 'processing', '2026-10-24', 'not_reviewed'],
  ['03', 'Documento de imagen · DEMO', 'imaging', 'ready_for_review', '2026-10-20', 'reviewed'],
  [
    '04',
    'Control de laboratorio · DEMO',
    'blood_test',
    'object_uploaded',
    '2026-10-16',
    'not_reviewed',
  ],
  ['05', 'Archivo de prueba · DEMO', 'other', 'failed', '2026-10-12', 'not_reviewed'],
  ['06', 'Informe de patología · DEMO', 'pathology', 'initiated', '2026-10-08', 'not_reviewed'],
  ['07', 'Documento anterior · DEMO', 'blood_test', 'ready_for_review', '2026-09-18', 'reviewed'],
].map(([id, title, test_type, status, test_date, review]) => ({
  clinical_test_id: `demo-exam-${id}`,
  patient_id: 'demo-patient',
  title: title!,
  test_type: test_type as Exam['test_type'],
  status: status as Exam['status'],
  test_date: test_date!,
  review: { status: review as Exam['review']['status'] },
  file: { name: `synthetic-document-${id}.pdf`, mime_type: 'application/pdf', size_bytes: 245760 },
  created_at: `${test_date}T10:00:00Z`,
  updated_at: `${test_date}T10:00:00Z`,
  notes: null,
}))
function check(signal?: AbortSignal) {
  signal?.throwIfAborted()
}
export const demoSource: ClinicalSource = {
  async list(filters, patientId, signal) {
    check(signal)
    if (patientId !== 'demo-patient') return { items: [], next_cursor: null }
    const filtered = items.filter(
      (x) =>
        (!filters.status || x.status === filters.status) &&
        (!filters.test_type || x.test_type === filters.test_type),
    )
    const offset = filters.cursor === 'demo-next-page' ? 6 : 0
    return {
      items: filtered.slice(offset, offset + 6),
      next_cursor: filtered.length > offset + 6 ? 'demo-next-page' : null,
    }
  },
  async detail(id, signal) {
    check(signal)
    const item = items.find((x) => x.clinical_test_id === id)
    if (!item) throw new ApiError(404, 'NOT_FOUND')
    return item
  },
  async catalog(signal) {
    check(signal)
    return [
      {
        marker_code: 'DEMO_MARKER',
        name: 'Marcador sintético / Synthetic marker',
        panel_code: 'DEMO',
        canonical_unit: '—',
        clinically_validated: false,
        catalog_version: 'demo-only',
      },
    ]
  },
}
