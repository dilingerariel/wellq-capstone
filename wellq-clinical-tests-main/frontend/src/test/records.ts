// Synthetic API fixtures only. Never imported by the application.
export const syntheticReport = (patient = 'synthetic-patient') => ({
  generated_at: '2026-11-01T12:00:00Z',
  header: {
    patient_id: patient,
    mode: 'aggregate',
    window: { months: 12, from: '2025-11-01', to: '2026-11-01' },
    exam: null,
    exams: [
      {
        clinical_test_id: 'synthetic-record',
        title: 'SYNTHETIC RECORD ONLY',
        test_date: '2026-02-01',
        validation_status: 'clinically_validated',
        review_status: 'reviewed',
      },
    ],
  },
  score: null,
  flags: [],
  longitudinal: null,
  imaging_findings: [],
  results: {
    panels: [
      {
        panel_code: 'metabolic',
        specimen: 'blood',
        rows: [
          {
            marker_code: 'glucose',
            name: 'Synthetic glucose',
            value: 98,
            unit: 'mg/dL',
            censoring: null,
            edited: true,
            reference: { low: 70, high: 110, unit: 'mg/dL', source: 'document' },
            status: 'normal',
            subscore: null,
            subscore_blank_reason: 'CATALOG_NOT_APPROVED',
            origin: { clinical_test_id: 'synthetic-record', measured_on: '2026-02-01' },
            original: { value_raw: '98', unit_raw: 'mg/dL', conversion_factor: 1 },
          },
        ],
      },
    ],
  },
  traceability: {
    scoring_version: 'synthetic-score-v1',
    catalog_version: 'synthetic-catalog-v1',
    excluded_markers: [{ marker_code: 'glucose', reason: 'CATALOG_NOT_APPROVED' }],
  },
})
export const syntheticSeries = (patient = 'synthetic-patient') => ({
  patient_id: patient,
  from: null,
  to: null,
  only_confirmed: true,
  series: [
    {
      marker_code: 'glucose',
      unit: 'mg/dL',
      points: [95, 98, null].map((value, i) => ({
        measured_on: `2026-0${i + 1}-01`,
        value,
        unit: 'mg/dL',
        reference: { low: 70, high: 110, unit: 'mg/dL', source: 'document' },
        status: 'normal',
        subscore: null,
        subscore_blank_reason: 'CATALOG_NOT_APPROVED',
        clinical_test_id: 'synthetic-record-' + i,
        confirmation_level: i ? 'clinician' : 'patient',
        edited: !!i,
      })),
    },
  ],
})
export const syntheticScores = (approved = true) => ({
  current_snapshot: {
    snapshot_id: 'synthetic-current',
    patient_id: 'synthetic-patient',
    computed_at: '2026-02-01T12:00:00Z',
    scoring_version: 'synthetic-v1',
    catalog_version: 'synthetic-catalog',
    catalog_clinically_approved: approved,
    lab_index: 0,
    pillars: {
      cardio: { score: 0, coverage: 0.7, confidence: 'medium', status: 'published' },
      bone: { score: null, coverage: 0.1, confidence: 'insufficient', status: 'insufficient_data' },
    },
  },
  history: [],
})
