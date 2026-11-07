import { useEffect, useSyncExternalStore } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useRuntime } from '../../app/runtime'
import { documentTypes, editable, identityRequired, lowCodes } from './model'
import '../../styles/review.css'

export function ReviewPage() {
  const { id = '' } = useParams(),
    { review, mode, canRequest, session } = useRuntime(),
    { t } = useTranslation()
  const s = useSyncExternalStore(review.subscribe, review.getSnapshot)
  useEffect(() => {
    if (mode === 'api' && canRequest && (!s.id || (s.id === id && s.phase === 'idle')))
      void review.load(id)
  }, [id, mode, canRequest, review, s.id, s.phase])
  useEffect(() => {
    if (!s.draft) return
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [s.draft])
  const ext = s.extraction,
    d = s.draft,
    locked = s.phase !== 'editing' || ext?.status !== 'awaiting_confirmation',
    mayConfirm = canRequest && session?.permissions.includes('extractions:confirm')
  function reset() {
    if (window.confirm(t('reviewResetWarning'))) {
      review.clear()
      void review.load(id)
    }
  }
  return (
    <div className="review-page">
      <Link className="back-link" to={`/exams/${encodeURIComponent(id)}`}>
        {t('back')}
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('reviewEyebrow')}</span>
          <h1>{t('reviewTitle')}</h1>
          <p>{t('reviewIntro')}</p>
        </div>
      </div>
      {mode === 'demo' ? (
        <section className="panel state">
          <p>{t('reviewDemo')}</p>
        </section>
      ) : s.id && s.id !== id ? (
        <section className="panel state">
          <p>{t('reviewOtherDraft')}</p>
          <Link to={`/exams/${encodeURIComponent(s.id)}/extraction`} className="button secondary">
            {t('reviewReturn')}
          </Link>
          <button className="button secondary" onClick={reset}>
            {t('reviewReset')}
          </button>
        </section>
      ) : (
        <>
          <p className="notice" role="status">
            {t(s.phase === 'done' ? 'reviewDone' : 'reviewMemory')}
          </p>
          {!canRequest && (
            <p role="status" className="notice">
              {t('reviewOffline')}
            </p>
          )}
          {s.error && (
            <div className="notice" role="alert">
              {t(s.error, { defaultValue: t('reviewServerError') })}
            </div>
          )}
          <div className="review-actions">
            <button
              className="button secondary"
              disabled={!canRequest || ['loading', 'sending', 'uncertain'].includes(s.phase)}
              onClick={() => void review.load(id)}
            >
              {t('reviewRefresh')}
            </button>
            {s.phase === 'conflict' && (
              <button className="button secondary" disabled={!canRequest} onClick={reset}>
                {t('reviewReset')}
              </button>
            )}
            {s.phase === 'uncertain' && (
              <button
                className="button primary"
                disabled={!mayConfirm}
                onClick={() => void review.confirm()}
              >
                {t('reviewRetry')}
              </button>
            )}
          </div>
          {s.document && (
            <section className="panel review-section">
              <h2>{s.document.title}</h2>
              <p>{s.document.file.name}</p>
              <p>
                {t('reviewDocumentId')}: {s.document.clinical_test_id}
              </p>
            </section>
          )}
          {ext && (
            <p role="status">
              {t('uploadExtraction')}: <strong>{t(`uploadExtraction_${ext.status}`)}</strong>
            </p>
          )}
          {ext && d && (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                review.review()
              }}
            >
              <fieldset disabled={locked} className="panel review-section">
                <legend>{t('reviewDocument')}</legend>
                <div className="review-fields">
                  <label>
                    {t('reviewCollection')}
                    <input
                      type="date"
                      value={d.collection_date}
                      onChange={(e) => review.update({ ...d, collection_date: e.target.value })}
                    />
                  </label>
                  <label>
                    {t('reviewReport')}
                    <input
                      type="date"
                      value={d.report_date}
                      onChange={(e) => review.update({ ...d, report_date: e.target.value })}
                    />
                  </label>
                  <label>
                    {t('reviewType')}
                    <select
                      value={d.document_type}
                      onChange={(e) =>
                        review.update({
                          ...d,
                          document_type: e.target.value as typeof d.document_type,
                        })
                      }
                    >
                      {documentTypes.map((type) => (
                        <option key={type} value={type}>
                          {t(`reviewType_${type}`)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {(!ext.document.collection_date || !ext.document.report_date) && (
                  <p>{t('reviewMissing')}</p>
                )}
                {ext.document.description && <p>{ext.document.description}</p>}
              </fieldset>
              {ext.panels.map((panel, pi) => (
                <section key={pi} className="review-section">
                  <h2>{panel.panel_name_raw || panel.panel_code}</h2>
                  {panel.collection_date && <p>{panel.collection_date}</p>}
                  <div className="review-markers">
                    {panel.markers.map((m, mi) => {
                      const code = m.marker_code,
                        draft = d.markers[code]!,
                        low = lowCodes(ext).includes(code)
                      return (
                        <fieldset className="panel review-marker" disabled={locked} key={mi}>
                          <legend>{m.raw_name || code}</legend>
                          <p>{code}</p>
                          <p>
                            {t('reviewOriginal')}: {m.value_raw || t('reviewAbsent')}{' '}
                            {m.unit_raw || t('reviewAbsent')}
                          </p>
                          <label>
                            {t('reviewValue')}
                            <input
                              aria-label={`${t('reviewValue')} ${code}`}
                              value={editable(ext, m) ? draft.value : m.value_raw}
                              readOnly={!editable(ext, m)}
                              maxLength={200}
                              onChange={(e) =>
                                review.update({
                                  ...d,
                                  markers: {
                                    ...d.markers,
                                    [code]: { ...draft, value: e.target.value },
                                  },
                                })
                              }
                            />
                          </label>
                          <label>
                            {t('reviewUnit')}
                            <input
                              aria-label={`${t('reviewUnit')} ${code}`}
                              value={editable(ext, m) ? draft.unit : m.unit_raw}
                              readOnly={!editable(ext, m)}
                              maxLength={100}
                              onChange={(e) =>
                                review.update({
                                  ...d,
                                  markers: {
                                    ...d.markers,
                                    [code]: { ...draft, unit: e.target.value },
                                  },
                                })
                              }
                            />
                          </label>
                          {!editable(ext, m) && <p>{t('reviewReadOnly')}</p>}
                          {(!m.value_raw || !m.unit_raw || m.validation?.passed === false) && (
                            <p>{t('reviewIncomplete')}</p>
                          )}
                          {m.reference && (
                            <div>
                              <strong>{t('reviewReference')}</strong>
                              <p>
                                {m.reference.text_raw ||
                                  `${m.reference.low ?? '—'} – ${m.reference.high ?? '—'}`}{' '}
                                {m.reference.unit}
                              </p>
                              <p>
                                {t('reviewSource')}: {m.reference.source || t('reviewAbsent')}
                              </p>
                            </div>
                          )}
                          {m.provenance && Object.keys(m.provenance).length > 0 && (
                            <details>
                              <summary>{t('reviewProvenance')}</summary>
                              <pre>{JSON.stringify(m.provenance, null, 2)}</pre>
                            </details>
                          )}
                          {m.confidence && (
                            <details open={low}>
                              <summary>{t('reviewConfidence')}</summary>
                              <ul>
                                {Object.entries(m.confidence).map(([k, v]) => (
                                  <li key={k}>
                                    {t(`reviewConfidence_${k}`, { defaultValue: k })}:{' '}
                                    {Math.round(v * 100)} %
                                  </li>
                                ))}
                              </ul>
                            </details>
                          )}
                        </fieldset>
                      )
                    })}
                  </div>
                </section>
              ))}
              <fieldset disabled={locked} className="panel review-section">
                <legend>{t('reviewAcknowledgmentsTitle')}</legend>
                {identityRequired(ext) && (
                  <label className="review-check">
                    <input
                      type="checkbox"
                      checked={d.identity}
                      onChange={(e) => review.update({ ...d, identity: e.target.checked })}
                    />
                    {t('reviewIdentity')}
                  </label>
                )}
                {lowCodes(ext).map((code) => (
                  <label className="review-check" key={code}>
                    <input
                      type="checkbox"
                      checked={d.acknowledged.includes(code)}
                      onChange={(e) =>
                        review.update({
                          ...d,
                          acknowledged: e.target.checked
                            ? [...d.acknowledged, code]
                            : d.acknowledged.filter((c) => c !== code),
                        })
                      }
                    />
                    {t('reviewLowAck', { code })}
                  </label>
                ))}
                <p>{t('reviewNoDiagnosis')}</p>
              </fieldset>
              {s.phase === 'editing' && ext.status === 'awaiting_confirmation' && (
                <button className="button primary" type="submit">
                  {t('reviewPreview')}
                </button>
              )}
            </form>
          )}
          {s.phase === 'reviewing' && ext && d && (
            <section className="panel review-section" aria-labelledby="review-summary">
              <h2 id="review-summary">{t('reviewSummary')}</h2>
              <ul>
                {(['collection_date', 'report_date', 'document_type'] as const)
                  .filter((k) => d[k] !== (ext.document[k] || ''))
                  .map((k) => (
                    <li key={k}>
                      {t(`reviewField_${k}`)}: {ext.document[k] || '—'} → {d[k]}
                    </li>
                  ))}
                {ext.panels
                  .flatMap((p) => p.markers)
                  .filter(
                    (m) =>
                      d.markers[m.marker_code]!.value !== m.value_raw ||
                      d.markers[m.marker_code]!.unit !== m.unit_raw,
                  )
                  .map((m) => (
                    <li key={m.marker_code}>
                      {m.raw_name}: {m.value_raw} {m.unit_raw} → {d.markers[m.marker_code]!.value}{' '}
                      {d.markers[m.marker_code]!.unit}
                    </li>
                  ))}
              </ul>
              <p>{t('reviewExplicit')}</p>
              <div className="review-actions">
                <button className="button secondary" onClick={() => review.edit()}>
                  {t('reviewBackEdit')}
                </button>
                <button
                  className="button primary"
                  disabled={!mayConfirm}
                  onClick={() => void review.confirm()}
                >
                  {t('reviewConfirm')}
                </button>
              </div>
            </section>
          )}
          {s.phase === 'sending' && <p role="status">{t('reviewSending')}</p>}
          {!mayConfirm && <p>{t('reviewPermission')}</p>}
        </>
      )}
    </div>
  )
}
