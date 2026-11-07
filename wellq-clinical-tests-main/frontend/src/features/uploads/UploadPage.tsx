import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { FileUp, ShieldCheck, X, RefreshCw } from 'lucide-react'
import { useRuntime } from '../../app/runtime'
import { testTypes } from '../../types/clinical'
import type { UploadMetadata } from './intent'
import { useUpload } from './UploadActivity'

export function UploadPage() {
  const { t } = useTranslation(),
    runtime = useRuntime(),
    { upload, state } = useUpload()
  const canAct =
    runtime.mode === 'api' &&
    runtime.canRequest &&
    runtime.role === 'patient' &&
    ['clinical:read', 'clinical:write'].every((permission) =>
      runtime.session?.permissions.includes(permission),
    )
  const progress =
    state.progress && state.progress.total > 0
      ? Math.floor(Math.min(100, (state.progress.loaded / state.progress.total) * 100))
      : null
  const update = (patch: Partial<UploadMetadata>) => upload.update(patch)
  const terminal = ['available', 'rejected', 'failed', 'deleted'].includes(state.phase)
  const error =
    state.error &&
    ([
      'uploadInvalidFile',
      'uploadInvalidSize',
      'uploadInvalidMetadata',
      'uploadPutFailed',
      'uploadInvalidStorage',
      'uploadExpiredUrl',
      'uploadConnectionRequired',
      'uploadRetryLater',
      'uploadNotConfirmed',
      'REQUEST_TIMEOUT',
      'INVALID_RESPONSE',
    ].includes(state.error) ||
      /^error_(0|400|401|403|404|409|413|422|429|500|502|503)$/.test(state.error))
      ? state.error
      : 'uploadUnknownError'
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('patient')}</span>
          <h1>{t('uploadTitle')}</h1>
          <p>{t('uploadSubtitle')}</p>
        </div>
        <ShieldCheck aria-hidden="true" />
      </div>
      <div className="upload-grid">
        <form
          className="panel upload-form"
          onSubmit={(event) => {
            event.preventDefault()
            if (canAct) void upload.run()
          }}
        >
          <div className="upload-picker">
            <FileUp size={30} aria-hidden="true" />
            <label htmlFor="clinical-file">{t('uploadSelect')}</label>
            <input
              id="clinical-file"
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.heic,application/pdf,image/jpeg,image/png,image/heic"
              disabled={state.locked || upload.busy}
              aria-describedby="upload-file-help"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) upload.select(file)
                event.target.value = ''
              }}
            />
            <p id="upload-file-help">{t('uploadFormats')}</p>
          </div>
          {state.file && (
            <div className="upload-file" aria-label={t('uploadSelected')}>
              <strong>{state.file.name}</strong>
              <span>{new Intl.NumberFormat().format(state.file.size)} B</span>
            </div>
          )}
          <fieldset disabled={state.locked || upload.busy}>
            <legend>{t('uploadMetadata')}</legend>
            <label htmlFor="upload-title">{t('uploadDocumentTitle')}</label>
            <input
              id="upload-title"
              value={state.metadata.title}
              required
              maxLength={200}
              autoComplete="off"
              onChange={(event) => update({ title: event.target.value })}
            />
            <div className="upload-fields">
              <div>
                <label htmlFor="upload-type">{t('filterType')}</label>
                <select
                  id="upload-type"
                  value={state.metadata.test_type}
                  onChange={(event) =>
                    update({ test_type: event.target.value as UploadMetadata['test_type'] })
                  }
                >
                  {testTypes.map((type) => (
                    <option key={type} value={type}>
                      {t(`type_${type}`)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="upload-date">{t('date')}</label>
                <input
                  type="date"
                  id="upload-date"
                  required
                  value={state.metadata.test_date}
                  onChange={(event) => update({ test_date: event.target.value })}
                />
              </div>
            </div>
            <label htmlFor="upload-notes">{t('uploadNotes')}</label>
            <textarea
              id="upload-notes"
              value={state.metadata.notes || ''}
              maxLength={2000}
              rows={3}
              autoComplete="off"
              onChange={(event) => update({ notes: event.target.value })}
            />
            <label className="upload-consent">
              <input
                type="checkbox"
                checked={state.metadata.ai_consent}
                onChange={(event) => update({ ai_consent: event.target.checked })}
              />
              <span>{t('uploadConsent')}</span>
            </label>
            <p className="subtext">{t('uploadConsentHelp')}</p>
          </fieldset>
          {runtime.mode === 'demo' ? (
            <p className="upload-notice">{t('uploadDemoBlocked')}</p>
          ) : (
            !canAct && <p className="upload-notice">{t('uploadConnectionRequired')}</p>
          )}
          {state.error && (
            <p role="alert" className="field-error">
              {t(
                error === 'REQUEST_TIMEOUT'
                  ? 'error_timeout'
                  : error === 'INVALID_RESPONSE'
                    ? 'error_502'
                    : error,
              )}
            </p>
          )}
          <div className="upload-actions">
            <button
              type="submit"
              className="button primary"
              disabled={!canAct || !state.file || upload.busy || terminal}
            >
              <FileUp size={18} aria-hidden="true" />
              {t(state.locked ? 'uploadRetry' : 'uploadSend')}
            </button>
            {upload.busy && (
              <button type="button" className="button secondary" onClick={() => upload.cancel()}>
                <X size={18} aria-hidden="true" />
                {t('uploadCancel')}
              </button>
            )}
            {state.file && (
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  if (window.confirm(t('uploadDiscardConfirm'))) upload.clear()
                }}
              >
                {t('uploadNew')}
              </button>
            )}
          </div>
        </form>
        <aside className="upload-side">
          <section className="panel upload-status" aria-labelledby="upload-status-title">
            <h2 id="upload-status-title">{t('uploadStatusTitle')}</h2>
            <p role="status" aria-live="polite">
              {t(`uploadPhase_${state.phase}`)}
            </p>
            {state.phase === 'uploading' && (
              <>
                <label htmlFor="upload-progress">{t('uploadByteProgress')}</label>
                <progress
                  id="upload-progress"
                  max={100}
                  {...(progress === null ? {} : { value: progress })}
                />
                <p>{progress === null ? t('uploadProgressUnknown') : `${progress} %`}</p>
              </>
            )}
            {!state.status && <p className="upload-notice">{t('uploadKeepOriginal')}</p>}
            {state.status && (
              <>
                <p>
                  {t('uploadServerState')}: <strong>{t(`status_${state.status.status}`)}</strong>
                </p>
                <ul>
                  <li>
                    {t('uploadScan')}: {t(`uploadCheck_${state.status.processing.malware_scan}`)}
                  </li>
                  <li>
                    {t('uploadMimeCheck')}:{' '}
                    {t(`uploadCheck_${state.status.processing.mime_validation}`)}
                  </li>
                </ul>
                {state.extraction && (
                  <p>
                    {t('uploadExtraction')}: {t(`uploadExtraction_${state.extraction}`)}
                  </p>
                )}
                <p
                  className={
                    state.status.local_file_can_be_deleted ? 'upload-verified' : 'upload-notice'
                  }
                >
                  {t(
                    state.status.local_file_can_be_deleted
                      ? 'uploadMayRemoveOriginal'
                      : 'uploadKeepOriginal',
                  )}
                </p>
                {state.status.status === 'ready_for_review' && (
                  <Link
                    className="button secondary"
                    to={`/exams/${encodeURIComponent(state.status.clinical_test_id)}`}
                  >
                    {t('uploadViewDocument')}
                  </Link>
                )}
                {state.extraction === 'awaiting_confirmation' && (
                  <Link
                    className="button primary"
                    to={`/exams/${encodeURIComponent(state.status.clinical_test_id)}/extraction`}
                  >
                    {t('reviewTitle')}
                  </Link>
                )}
              </>
            )}
            {state.phase === 'poll-limit' && (
              <button
                type="button"
                className="button secondary"
                disabled={!canAct || upload.busy}
                onClick={() => void upload.run()}
              >
                <RefreshCw size={16} aria-hidden="true" />
                {t('uploadCheckAgain')}
              </button>
            )}
          </section>
          <section className="panel upload-status">
            <h2>{t('uploadPrivacyTitle')}</h2>
            <p>{t('uploadMemoryHelp')}</p>
            <p>{t('uploadNoResumePromise')}</p>
            <p>{t('uploadNoAutomaticDelete')}</p>
          </section>
        </aside>
      </div>
    </>
  )
}
