import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronLeft, ChevronRight, RefreshCw, SlidersHorizontal } from 'lucide-react'
import { ExamTable } from '../../components/ExamTable'
import { Empty, ErrorState, Loading } from '../../components/States'
import { statuses, testTypes, type ExamFilters } from '../../types/clinical'
import { useExams } from './useExams'
import { useRuntime } from '../../app/runtime'
import { CachedNotice, NeedsConnection } from '../../components/Continuity'

export function ExamsPage() {
  const { t } = useTranslation()
  const { canRequest } = useRuntime()
  const [filters, setFilters] = useState<ExamFilters>({})
  const [cursors, setCursors] = useState<Array<string | undefined>>([undefined])
  const query = useExams({ ...filters, cursor: cursors.at(-1) })
  const update = (value: ExamFilters) => {
    setFilters(value)
    setCursors([undefined])
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('workspace')}</span>
          <h1>{t('examTitle')}</h1>
          <p>{t('examSubtitle')}</p>
        </div>
        <button
          className="button secondary"
          disabled={!canRequest || !query.allowed || query.needsPatient || query.isFetching}
          onClick={() => void query.refetch()}
        >
          <RefreshCw size={16} aria-hidden="true" />
          {t('refresh')}
        </button>
      </div>
      <CachedNotice error={query.isError} />
      <section className="panel">
        <div className="filter-bar">
          <SlidersHorizontal size={18} aria-hidden="true" />
          <div>
            <label htmlFor="status-filter" className="filter-label">
              {t('filterStatus')}
            </label>
            <select
              id="status-filter"
              value={filters.status || ''}
              onChange={(e) =>
                update({
                  ...filters,
                  status: (e.target.value as ExamFilters['status']) || undefined,
                })
              }
            >
              <option value="">{t('allStatuses')}</option>
              {statuses.map((s) => (
                <option value={s} key={s}>
                  {t(`status_${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="type-filter" className="filter-label">
              {t('filterType')}
            </label>
            <select
              id="type-filter"
              value={filters.test_type || ''}
              onChange={(e) =>
                update({
                  ...filters,
                  test_type: (e.target.value as ExamFilters['test_type']) || undefined,
                })
              }
            >
              <option value="">{t('allTypes')}</option>
              {testTypes.map((s) => (
                <option value={s} key={s}>
                  {t(`type_${s}`)}
                </option>
              ))}
            </select>
          </div>
          {(filters.status || filters.test_type) && (
            <button className="text-button" onClick={() => update({})}>
              {t('clearFilters')}
            </button>
          )}
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
        ) : query.data.items.length === 0 ? (
          <Empty />
        ) : (
          <ExamTable items={query.data.items} />
        )}
        <div className="pagination">
          <span>{t('page', { number: cursors.length })}</span>
          <div>
            <button
              className="button secondary"
              disabled={cursors.length === 1 || query.isFetching}
              onClick={() => setCursors((c) => c.slice(0, -1))}
            >
              <ChevronLeft size={16} aria-hidden="true" />
              {t('previous')}
            </button>
            <button
              className="button secondary"
              disabled={!query.data?.next_cursor || query.isFetching}
              onClick={() => setCursors((c) => [...c, query.data?.next_cursor || undefined])}
            >
              {t('next')}
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>
    </>
  )
}
