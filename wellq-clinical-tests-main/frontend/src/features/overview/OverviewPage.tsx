import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  ArrowRight,
  Files,
  ClipboardCheck,
  Clock3,
  ArrowUpRight,
  ShieldCheck,
  UploadCloud,
} from 'lucide-react'
import { useRuntime } from '../../app/runtime'
import { useExams } from '../exams/useExams'
import { ExamTable } from '../../components/ExamTable'
import { Loading, Empty, ErrorState } from '../../components/States'
import { CachedNotice, NeedsConnection } from '../../components/Continuity'
import { UploadPreparation } from '../uploads/UploadPreparation'
export function OverviewPage() {
  const { t } = useTranslation()
  const { role, canRequest } = useRuntime()
  const query = useExams()
  const items = query.data?.items
  const cards = [
    { label: 'pageCount', value: items?.length, Icon: Files },
    {
      label: 'reviewCount',
      value: items?.filter(
        (x) => x.status === 'ready_for_review' && x.review.status === 'not_reviewed',
      ).length,
      Icon: ClipboardCheck,
    },
    {
      label: 'processingCount',
      value: items?.filter((x) => x.status === 'processing').length,
      Icon: Clock3,
    },
  ]
  return (
    <>
      <section className="hero">
        <div>
          <span className="eyebrow">{t('welcomeLabel')}</span>
          <h1>{t(role === 'clinician' ? 'clinicalTitle' : 'overviewTitle')}</h1>
          <p>{t(role === 'clinician' ? 'clinicalSubtitle' : 'overviewSubtitle')}</p>
          <Link className="button primary" to="/exams">
            {t('viewAll')}
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </div>
        <div className="hero-mark" aria-hidden="true">
          <ShieldCheck size={64} strokeWidth={1.25} />
        </div>
      </section>
      <div className="metric-grid">
        {cards.map(({ label, value, Icon }) => (
          <article className="metric" key={label}>
            <div className="metric-top">
              <span>{t(label)}</span>
              <Icon size={20} aria-hidden="true" />
            </div>
            <strong>{query.isError || query.needsPatient ? '—' : (value ?? '—')}</strong>
          </article>
        ))}
      </div>
      <p className="small-note">{t('pageOnly')}</p>
      <CachedNotice error={query.isError} />
      <section className="panel">
        <div className="panel-heading">
          <h2>{t('recent')}</h2>
          <Link className="text-link" to="/exams">
            {t('exams')}
            <ArrowUpRight size={15} aria-hidden="true" />
          </Link>
        </div>
        {!query.allowed ? (
          <Empty description="noGrant" />
        ) : query.needsPatient ? (
          <Empty description="noPatient" />
        ) : query.isError && !query.data ? (
          <ErrorState
            error={query.error}
            retry={canRequest ? () => void query.refetch() : undefined}
          />
        ) : !canRequest && !query.data ? (
          <NeedsConnection />
        ) : !query.data ? (
          <Loading />
        ) : !items?.length ? (
          <Empty />
        ) : (
          <ExamTable items={items.slice(0, 4)} />
        )}
      </section>
      {role === 'patient' && <UploadPreparation />}
      <div className="next-grid">
        <article className="next-card">
          <span className="file-icon">
            <UploadCloud size={21} aria-hidden="true" />
          </span>
          <div>
            <h2>{t('newUpload')}</h2>
            <p>{t('uploadPending')}</p>
            <span className="pending-label">{t('pending')}</span>
          </div>
        </article>
        <article className="next-card">
          <span className="file-icon">
            <ShieldCheck size={21} aria-hidden="true" />
          </span>
          <div>
            <h2>{t('clinicalPending')}</h2>
            <p>{t(role === 'clinician' ? 'clinicalPendingBody' : 'patientPendingBody')}</p>
            <span className="pending-label">{t('pending')}</span>
          </div>
        </article>
      </div>
    </>
  )
}
