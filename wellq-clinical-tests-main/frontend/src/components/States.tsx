import { AlertCircle, FileSearch, LoaderCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../services/http'
export function Loading() {
  const { t } = useTranslation()
  return (
    <div role="status" className="state">
      <LoaderCircle className="spin" aria-hidden="true" />
      <p>{t('loading')}</p>
    </div>
  )
}
export function Empty({ description = 'emptyBody' }: { description?: string }) {
  const { t } = useTranslation()
  return (
    <div className="state">
      <span className="state-icon">
        <FileSearch aria-hidden="true" />
      </span>
      <h2>{t('emptyTitle')}</h2>
      <p>{t(description)}</p>
    </div>
  )
}
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const { t } = useTranslation()
  const status = error instanceof ApiError ? error.status : 'unknown'
  const known = [0, 401, 403, 404, 409, 422, 429, 503, 502].includes(Number(status))
  return (
    <div role="alert" className="state error">
      <AlertCircle aria-hidden="true" />
      <h2>{t('errorTitle')}</h2>
      <p>{t(known ? `error_${status}` : 'error_unknown')}</p>
      {retry && (
        <button className="button secondary" onClick={retry}>
          {t('retry')}
        </button>
      )}
    </div>
  )
}
