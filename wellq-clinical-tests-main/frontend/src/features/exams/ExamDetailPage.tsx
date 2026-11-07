import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, FileText, Info } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useRuntime } from '../../app/runtime'
import { ErrorState, Loading } from '../../components/States'
import { StatusBadge } from '../../components/StatusBadge'
import { formatDate } from '../../lib/format'
import { CachedNotice, NeedsConnection } from '../../components/Continuity'
import { usePatientScope } from './PatientScope'
import { ApiError } from '../../services/http'
export function ExamDetailPage() {
  const { id = '' } = useParams()
  const { source, canRequest, role, mode } = useRuntime()
  const { patientId } = usePatientScope()
  const { t, i18n } = useTranslation()
  const query = useQuery({
    queryKey: ['exam', id],
    queryFn: ({ signal }) => source!.detail(id, signal),
    enabled: Boolean(source && id && canRequest),
    refetchInterval: (q) =>
      canRequest &&
      ['initiated', 'object_uploaded', 'processing'].includes(q.state.data?.status || '')
        ? 10_000
        : false,
  })
  if (query.isError && !query.data)
    return (
      <ErrorState error={query.error} retry={canRequest ? () => void query.refetch() : undefined} />
    )
  if (!query.data && !canRequest) return <NeedsConnection />
  if (!query.data) return <Loading />
  const exam = query.data
  if (patientId && exam.patient_id !== patientId)
    return <ErrorState error={new ApiError(403, 'PATIENT_CONTEXT_MISMATCH')} />
  const details = [
    ['type', t(`type_${exam.test_type}`)],
    ['date', formatDate(exam.test_date, i18n.language)],
    ['review', t(`review_${exam.review.status}`)],
    ['filename', exam.file.name],
    ['filetype', exam.file.mime_type],
    [
      'filesize',
      new Intl.NumberFormat(i18n.language, {
        style: 'unit',
        unit: 'kilobyte',
        maximumFractionDigits: 1,
      }).format(exam.file.size_bytes / 1024),
    ],
    ['created', formatDate(exam.created_at, i18n.language)],
  ]
  return (
    <>
      <CachedNotice error={query.isError} />
      <Link to="/exams" className="back-link">
        <ArrowLeft size={16} aria-hidden="true" />
        {t('back')}
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('examDetail')}</span>
          <h1>{exam.title}</h1>
        </div>
        <StatusBadge status={exam.status} />
      </div>
      <section className="panel detail-panel">
        {role === 'clinician' && mode === 'api' && (
          <Link className="button primary" to={`/exams/${encodeURIComponent(id)}/clinical-review`}>
            {t('clinicalWorkTitle')}
          </Link>
        )}
        {role === 'patient' && mode === 'api' && (
          <Link className="button secondary" to={`/exams/${encodeURIComponent(id)}/extraction`}>
            {t('reviewTitle')}
          </Link>
        )}
        <h2>
          <FileText size={19} aria-hidden="true" />
          {t('documentInfo')}
        </h2>
        <dl className="details">
          {details.map(([key, value]) => (
            <div key={key}>
              <dt>{t(key!)}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <div className="notes">
          <h3>{t('notes')}</h3>
          <p>{exam.notes || t('noNotes')}</p>
        </div>
      </section>
      <aside className="notice">
        <Info size={19} aria-hidden="true" />
        <p>{t('detailNotice')}</p>
      </aside>
    </>
  )
}
