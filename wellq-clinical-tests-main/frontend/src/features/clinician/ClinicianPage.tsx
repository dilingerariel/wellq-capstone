import { useEffect, useSyncExternalStore } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useRuntime } from '../../app/runtime'
import { usePatientScope } from '../exams/PatientScope'
import { editable } from '../review/model'
import '../../styles/review.css'
export function ClinicianPage() {
  const { id = '' } = useParams(),
    { clinician, mode, canRequest, session } = useRuntime(),
    { patientId } = usePatientScope(),
    { t } = useTranslation()
  const s = useSyncExternalStore(clinician.subscribe, clinician.getSnapshot)
  useEffect(() => {
    if (mode === 'api' && canRequest && patientId && (!s.id || (s.id === id && s.phase === 'idle')))
      void clinician.load(id, patientId)
  }, [mode, canRequest, patientId, id, s.id, s.phase, clinician])
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (clinician.hasWork()) {
        e.preventDefault()
        e.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [clinician])
  const doc = s.document,
    ext = s.extraction,
    d = s.draft,
    locked = s.phase !== 'editing',
    grant = (p: string) => !!session?.permissions.includes(p)
  const reset = () => {
    if (!clinician.hasWork() || window.confirm(t('clinicalDiscard'))) {
      clinician.clear()
      void clinician.load(id, patientId)
    }
  }
  if (mode !== 'api')
    return (
      <section className="panel state">
        <h1>{t('clinicalWorkTitle')}</h1>
        <p>{t('clinicalDemo')}</p>
      </section>
    )
  if (!patientId)
    return (
      <section className="panel state">
        <h1>{t('clinicalWorkTitle')}</h1>
        <p>{t('noPatient')}</p>
      </section>
    )
  if (s.id && (s.id !== id || s.patient !== patientId))
    return (
      <section className="panel state">
        <h1>{t('clinicalWorkTitle')}</h1>
        <p>{t('clinicalOtherDraft')}</p>
        <Link
          className="button secondary"
          to={`/exams/${encodeURIComponent(s.id)}/clinical-review`}
        >
          {t('reviewReturn')}
        </Link>
        <button className="button secondary" disabled={!canRequest} onClick={reset}>
          {t('clinicalLoad')}
        </button>
      </section>
    )
  return (
    <div className="review-page">
      <Link className="back-link" to={`/exams/${encodeURIComponent(id)}`}>
        {t('back')}
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('clinicalEyebrow')}</span>
          <h1>{t('clinicalWorkTitle')}</h1>
          <p>{t('clinicalIntro')}</p>
        </div>
      </div>
      <p className="notice" role="status">
        {t(s.phase === 'done' ? 'clinicalDone' : 'clinicalMemory')}
      </p>
      {!canRequest && <p role="status">{t('reviewOffline')}</p>}
      {s.error && (
        <p className="notice" role="alert">
          {t(s.error, { defaultValue: t('reviewServerError') })}
        </p>
      )}
      <div className="review-actions">
        <button
          className="button secondary"
          disabled={
            !canRequest || ['sending', 'loading', 'uncertain', 'conflict'].includes(s.phase)
          }
          onClick={() => void clinician.load(id, patientId)}
        >
          {t('reviewRefresh')}
        </button>
        {['conflict', 'done'].includes(s.phase) && (
          <button className="button secondary" disabled={!canRequest} onClick={reset}>
            {t('clinicalLoad')}
          </button>
        )}
        {s.phase === 'uncertain' && (
          <button
            className="button secondary"
            disabled={!canRequest}
            onClick={() => void clinician.reconcile()}
          >
            {t('clinicalReconcile')}
          </button>
        )}
      </div>
      {doc && (
        <section className="panel review-section">
          <h2>{doc.title}</h2>
          <p>{doc.file.name}</p>
          <p>
            {t('patientContext')}: {doc.patient_id}
          </p>
          <p>
            {t('reviewDocumentId')}: {doc.clinical_test_id}
          </p>
          <p>
            {t('review')}: <strong>{t(`review_${doc.review.status}`)}</strong>
          </p>
          {doc.review.reviewed_by && (
            <p>
              {t('clinicalReviewer')}: {doc.review.reviewed_by}
            </p>
          )}
          {doc.review.reviewed_at && <p>{doc.review.reviewed_at}</p>}
        </section>
      )}
      {s.extractionUnavailable && (
        <p className="notice" role="status">
          {t('clinicalUnavailable')}
        </p>
      )}
      {ext && (
        <section className="review-section">
          <h2>{t('clinicalExtraction')}</h2>
          <p role="status">{t(`uploadExtraction_${ext.status}`)}</p>
          {ext.confirmation.validated_by && (
            <p>
              {t('clinicalValidator')}: {ext.confirmation.validated_by}
            </p>
          )}
          {ext.confirmation.validated_at && <p>{ext.confirmation.validated_at}</p>}
          <div className="review-markers">
            {ext.panels.map((p, pi) => (
              <section key={pi}>
                <h3>{p.panel_name_raw}</h3>
                {p.markers.map((m, mi) => {
                  const v = d.markers[m.marker_code] || {
                      value: m.value_raw,
                      unit: m.unit_raw,
                      reason: '',
                    },
                    canEdit =
                      editable(ext, m) &&
                      m.validation?.passed !== false &&
                      ext.status === 'confirmed' &&
                      grant('extractions:validate')
                  return (
                    <fieldset
                      className="panel review-marker"
                      key={mi}
                      disabled={locked || !canEdit}
                    >
                      <legend>{m.raw_name}</legend>
                      <p>{m.marker_code}</p>
                      <p>
                        {t('reviewOriginal')}: {m.value_raw} {m.unit_raw}
                      </p>
                      <label>
                        {t('reviewValue')}
                        <input
                          aria-label={`${t('reviewValue')} ${m.marker_code}`}
                          maxLength={200}
                          value={v.value}
                          onChange={(e) =>
                            clinician.update({
                              ...d,
                              markers: {
                                ...d.markers,
                                [m.marker_code]: { ...v, value: e.target.value },
                              },
                            })
                          }
                        />
                      </label>
                      <label>
                        {t('reviewUnit')}
                        <input
                          aria-label={`${t('reviewUnit')} ${m.marker_code}`}
                          maxLength={100}
                          value={v.unit}
                          onChange={(e) =>
                            clinician.update({
                              ...d,
                              markers: {
                                ...d.markers,
                                [m.marker_code]: { ...v, unit: e.target.value },
                              },
                            })
                          }
                        />
                      </label>
                      <label>
                        {t('clinicalReason')}
                        <input
                          aria-label={`${t('clinicalReason')} ${m.marker_code}`}
                          maxLength={1000}
                          value={v.reason}
                          onChange={(e) =>
                            clinician.update({
                              ...d,
                              markers: {
                                ...d.markers,
                                [m.marker_code]: { ...v, reason: e.target.value },
                              },
                            })
                          }
                        />
                      </label>
                      {(m.validation?.passed === false ||
                        ext.flags.some((f) => f.marker_code === m.marker_code)) && (
                        <p>{t('clinicalAttention')}</p>
                      )}
                      {s.issues
                        .filter((i) => i.marker_code === m.marker_code)
                        .map((issue, i) => (
                          <p role="alert" key={i}>
                            {t(issue.code, { defaultValue: t('clinicalInvalid') })}
                          </p>
                        ))}
                      {m.reference && (
                        <p>
                          {t('reviewReference')}:{' '}
                          {m.reference.text_raw ||
                            `${m.reference.low ?? '—'} – ${m.reference.high ?? '—'}`}{' '}
                          {m.reference.unit} ({m.reference.source})
                        </p>
                      )}
                      {m.provenance && (
                        <details>
                          <summary>{t('reviewProvenance')}</summary>
                          <pre>{JSON.stringify(m.provenance, null, 2)}</pre>
                        </details>
                      )}
                    </fieldset>
                  )
                })}
              </section>
            ))}
          </div>
        </section>
      )}
      {doc && (
        <>
          <section className="panel review-section">
            <h2>{t('clinicalDocumentReview')}</h2>
            <p>{t('clinicalReviewHelp')}</p>
            <label>
              {t('clinicalReviewNote')}
              <textarea
                rows={4}
                maxLength={2000}
                value={d.reviewNote}
                disabled={
                  locked || doc.review.status !== 'not_reviewed' || !grant('clinical:review')
                }
                onChange={(e) => clinician.update({ ...d, reviewNote: e.target.value })}
              />
            </label>
            <button
              className="button primary"
              disabled={
                locked ||
                !canRequest ||
                !grant('clinical:review') ||
                doc.status !== 'ready_for_review' ||
                doc.review.status !== 'not_reviewed'
              }
              onClick={() => clinician.preview('review')}
            >
              {t('clinicalPrepareReview')}
            </button>
          </section>
          <section className="panel review-section">
            <h2>{t('clinicalValidation')}</h2>
            <p>{t('clinicalValidationHelp')}</p>
            <label>
              {t('clinicalNote')}
              <textarea
                rows={4}
                maxLength={2000}
                value={d.clinicalNote}
                disabled={locked || ext?.status !== 'confirmed' || !grant('extractions:validate')}
                onChange={(e) => clinician.update({ ...d, clinicalNote: e.target.value })}
              />
            </label>
            <div className="review-actions">
              <button
                className="button primary"
                disabled={
                  locked ||
                  !canRequest ||
                  !grant('extractions:validate') ||
                  ext?.status !== 'confirmed'
                }
                onClick={() => clinician.preview('validated')}
              >
                {t('clinicalPrepareValidate')}
              </button>
              <button
                className="button secondary"
                disabled={
                  locked ||
                  !canRequest ||
                  !grant('extractions:validate') ||
                  ext?.status !== 'confirmed'
                }
                onClick={() => clinician.preview('rejected')}
              >
                {t('clinicalPrepareReject')}
              </button>
            </div>
          </section>
        </>
      )}
      {s.phase === 'preview' && (
        <section className="panel review-section">
          <h2>{t('clinicalPreview')}</h2>
          <p>{t(`clinicalAction_${s.action}`)}</p>
          <p>{t('clinicalExplicit')}</p>
          {s.action === 'review' ? (
            <p>
              {t('clinicalReviewNote')}: {d.reviewNote || '—'}
            </p>
          ) : (
            <>
              <p>
                {t('clinicalNote')}: {d.clinicalNote || '—'}
              </p>
              <ul>
                {ext?.panels
                  .flatMap((p) => p.markers)
                  .filter(
                    (m) =>
                      d.markers[m.marker_code]!.value !== m.value_raw ||
                      d.markers[m.marker_code]!.unit !== m.unit_raw,
                  )
                  .map((m) => (
                    <li key={m.marker_code}>
                      {m.raw_name}: {m.value_raw} {m.unit_raw} → {d.markers[m.marker_code]!.value}{' '}
                      {d.markers[m.marker_code]!.unit} ({d.markers[m.marker_code]!.reason})
                    </li>
                  ))}
              </ul>
            </>
          )}
          <div className="review-actions">
            <button className="button secondary" onClick={() => clinician.edit()}>
              {t('reviewBackEdit')}
            </button>
            <button
              className="button primary"
              disabled={!canRequest}
              onClick={() => void clinician.send()}
            >
              {t(`clinicalSend_${s.action}`)}
            </button>
          </div>
        </section>
      )}
      {s.phase === 'sending' && <p role="status">{t('reviewSending')}</p>}
    </div>
  )
}
