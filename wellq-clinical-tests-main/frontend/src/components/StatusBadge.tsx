import { CheckCircle2, Circle, Clock3, AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { UploadStatus } from '../types/api.generated'
export function StatusBadge({ status }: { status: UploadStatus }) {
  const { t } = useTranslation()
  const Icon =
    status === 'ready_for_review'
      ? CheckCircle2
      : status === 'processing'
        ? Clock3
        : ['failed', 'rejected'].includes(status)
          ? AlertCircle
          : Circle
  return (
    <span className={`badge status-${status}`}>
      <Icon size={13} aria-hidden="true" />
      {t(`status_${status}`)}
    </span>
  )
}
