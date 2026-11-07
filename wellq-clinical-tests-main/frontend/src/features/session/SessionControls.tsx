import { ShieldCheck, LogIn, LogOut, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
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
          {runtime.canRenew && (
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
  return (
    <section className="panel state">
      <ShieldCheck size={35} aria-hidden="true" />
      <h1>{t(runtime.loading ? 'loadingSession' : 'sessionPending')}</h1>
      <p>{t('sessionHelp')}</p>
      <p role="status">{t(`session_${runtime.sessionPhase}`)}</p>
      <div className="session-actions">
        {runtime.canSignIn && (
          <button
            className="button primary"
            disabled={runtime.loading || runtime.connection !== 'online'}
            onClick={runtime.signIn}
          >
            <LogIn size={17} aria-hidden="true" />
            {t('signIn')}
          </button>
        )}
        <button
          className="button secondary"
          disabled={runtime.loading || runtime.connection !== 'online'}
          onClick={runtime.reloadIdentity}
        >
          {t('reloadIdentity')}
        </button>
      </div>
    </section>
  )
}
