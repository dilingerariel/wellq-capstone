import { useEffect, useSyncExternalStore } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useRuntime } from '../../app/runtime'
export function useUpload() {
  const { upload } = useRuntime()
  return { upload, state: useSyncExternalStore(upload.subscribe, upload.getSnapshot) }
}
export function UploadActivity() {
  const { t } = useTranslation(),
    { state } = useUpload(),
    location = useLocation()
  useEffect(() => {
    if (!state.file || state.status?.local_file_can_be_deleted) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [state.file, state.status?.local_file_can_be_deleted])
  if (!state.file || location.pathname === '/upload') return null
  return (
    <div className="upload-activity" role="status">
      <span>{t('uploadInMemory')}</span>
      <Link to="/upload">{t('uploadReturn')}</Link>
    </div>
  )
}
