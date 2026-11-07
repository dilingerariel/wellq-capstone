import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useRuntime } from '../../app/runtime'
import { Empty, ErrorState, Loading } from '../../components/States'
import { CachedNotice, NeedsConnection } from '../../components/Continuity'
export function CatalogPage() {
  const { source, canRequest } = useRuntime()
  const { t } = useTranslation()
  const query = useQuery({
    queryKey: ['catalog'],
    queryFn: ({ signal }) => source!.catalog(signal),
    enabled: Boolean(source && canRequest),
  })
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('resources')}</span>
          <h1>{t('catalog')}</h1>
          <p>{t('catalogSubtitle')}</p>
        </div>
      </div>
      <CachedNotice error={query.isError} />
      <section className="panel">
        {query.isError && !query.data ? (
          <ErrorState
            error={query.error}
            retry={canRequest ? () => void query.refetch() : undefined}
          />
        ) : !query.data && !canRequest ? (
          <NeedsConnection />
        ) : !query.data ? (
          <Loading />
        ) : !query.data.length ? (
          <Empty description="catalogEmpty" />
        ) : (
          <div className="table-scroll" role="region" aria-label={t('catalog')} tabIndex={0}>
            <table className="responsive-table">
              <caption className="sr-only">{t('catalog')}</caption>
              <thead>
                <tr>
                  {['code', 'document', 'unit', 'validation'].map((s) => (
                    <th key={s} scope="col">
                      {t(s)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.map((item) => (
                  <tr key={item.marker_code}>
                    <td data-label={t('code')}>
                      <code>{item.marker_code}</code>
                    </td>
                    <td data-label={t('document')}>{item.name}</td>
                    <td data-label={t('unit')}>{item.canonical_unit}</td>
                    <td data-label={t('validation')}>
                      <span className="review-label">
                        {t(item.clinically_validated ? 'validated' : 'notValidated')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
