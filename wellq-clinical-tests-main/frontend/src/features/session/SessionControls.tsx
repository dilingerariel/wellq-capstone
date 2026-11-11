import { Activity, LockKeyhole, LogIn, LogOut, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'
import { useRuntime } from '../../app/runtime'

export function SessionControls() {
  const { t } = useTranslation()
  const runtime = useRuntime()
  if (runtime.mode !== 'api') return null
  return (
    <div className="session-controls">
      <span className="review-label" role="status">
        {t(`session_${runtime.sessionPhase}`)}
      </span>
      {runtime.session && (
        <>
          {(runtime.canRenew || runtime.sessionPhase === 'unverified') && (
            <button
              className="icon-button"
              disabled={runtime.loading || runtime.connection !== 'online'}
              aria-label={t('renewSession')}
              onClick={runtime.reloadIdentity}
            >
              <RefreshCw size={18} aria-hidden="true" />
            </button>
          )}
          <button className="button secondary" onClick={runtime.signOut}>
            <LogOut size={16} aria-hidden="true" />
            {t('signOut')}
          </button>
        </>
      )}
    </div>
  )
}
export function SessionGate() {
  const { t } = useTranslation()
  const runtime = useRuntime()
  const { pathname } = useLocation()
  // Presentation only. The identity provider and backend still decide the role.
  const patientEntry =
    /^\/(patient|upload)(\/|$)/.test(pathname) || pathname.endsWith('/extraction')
  const disabled = runtime.loading || runtime.connection !== 'online'
  return (
    <section className="access-card" aria-labelledby="access-title" aria-busy={runtime.loading}>
      <div className="access-brand">
        <span className="access-mark">
          <Activity size={27} aria-hidden="true" />
        </span>
        <span>
          {t('brand')}
          <small>{t(patientEntry ? 'portal' : 'accessClinical')}</small>
        </span>
      </div>
      <div className="access-intro">
        <h1 id="access-title">{t(patientEntry ? 'accessPatient' : 'accessProfessional')}</h1>
        <p>{t(patientEntry ? 'accessPatientIntro' : 'accessProfessionalIntro')}</p>
      </div>
      <div
        className={`access-status${runtime.sessionPhase === 'error' ? ' access-status-error' : ''}`}
        role={runtime.sessionPhase === 'error' ? 'alert' : 'status'}
      >
        {runtime.loading && <RefreshCw className="access-spinner" size={18} aria-hidden="true" />}
        <span>{t(`session_${runtime.sessionPhase}`)}</span>
      </div>
      <p className="access-help">
        {t(runtime.canSignIn ? 'accessDelegatedHelp' : 'accessProviderHelp')}
      </p>
      <div className="session-actions access-actions">
        {runtime.canSignIn && (
          <button className="button primary" disabled={disabled} onClick={runtime.signIn}>
            <LogIn size={17} aria-hidden="true" />
            {t(runtime.loading ? 'loadingSession' : patientEntry ? 'signIn' : 'accessEnter')}
          </button>
        )}
        <button className="button secondary" disabled={disabled} onClick={runtime.reloadIdentity}>
          <RefreshCw size={17} aria-hidden="true" />
          {t('reloadIdentity')}
        </button>
      </div>
      {runtime.connection !== 'online' && <p className="access-offline">{t('accessOffline')}</p>}
      <p className="access-footnote">
        <LockKeyhole size={16} aria-hidden="true" />
        {t('accessScope')}
      </p>
    </section>
  )
}
