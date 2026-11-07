import { useSyncExternalStore } from 'react'
import { useTranslation } from 'react-i18next'
import { WifiOff, RefreshCw, Download } from 'lucide-react'
import { useRuntime } from '../app/runtime'
import { pwa } from '../services/pwa'

export function ConnectionIndicator() {
  const { t } = useTranslation()
  const { mode, connection } = useRuntime()
  return (
    <span className={`connection-indicator connection-${connection}`} role="status">
      {t(
        mode === 'demo' && connection === 'online' ? 'connection_demo' : `connection_${connection}`,
      )}
    </span>
  )
}
export function ContinuityBanner() {
  const { t } = useTranslation()
  const { connection, checkConnection, mode } = useRuntime()
  const update = useSyncExternalStore(pwa.subscribe, pwa.getSnapshot)
  return (
    <>
      {!['checking', 'online'].includes(connection) && (
        <section className="continuity-banner" aria-label={t('connectionStatus')}>
          <WifiOff size={18} aria-hidden="true" />
          <div role="status">
            <strong>{t(`connection_${connection}`)}</strong>
            <p>{t(mode === 'demo' ? 'demoOfflineHelp' : 'offlineHelp')}</p>
          </div>
          <button className="button secondary" onClick={checkConnection}>
            <RefreshCw size={16} aria-hidden="true" />
            {t('checkConnection')}
          </button>
        </section>
      )}
      {update.updateReady && (
        <section className="continuity-banner">
          <Download size={18} aria-hidden="true" />
          <p>{t('updateReady')}</p>
          <button
            className="button secondary"
            onClick={() => {
              if (window.confirm(t('updateConfirm'))) pwa.apply()
            }}
          >
            {t('applyUpdate')}
          </button>
        </section>
      )}
    </>
  )
}
export function CachedNotice({ error = false }: { error?: boolean }) {
  const { t } = useTranslation()
  const { mode, canRequest, loading } = useRuntime()
  return mode === 'api' && (!canRequest || error || loading) ? (
    <p className="cached-notice" role="status">
      {t('cachedInMemory')}
    </p>
  ) : null
}
export function NeedsConnection() {
  const { t } = useTranslation()
  const { checkConnection } = useRuntime()
  return (
    <section className="state" role="status">
      <WifiOff aria-hidden="true" />
      <h2>{t('needsConnection')}</h2>
      <p>{t('offlineHelp')}</p>
      <button className="button secondary" onClick={checkConnection}>
        {t('checkConnection')}
      </button>
    </section>
  )
}
