import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useRuntime } from '../../app/runtime'
import { Empty, ErrorState, Loading } from '../../components/States'
export function CatalogPage() {
  const { source } = useRuntime()
  const { t } = useTranslation()
  const query = useQuery({
    queryKey: ['catalog'],
    queryFn: ({ signal }) => source!.catalog(signal),
    enabled: Boolean(source),
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
      <section className="panel">
        {query.isError ? (
          <ErrorState error={query.error} retry={() => void query.refetch()} />
        ) : query.isPending ? (
          <Loading />
        ) : !query.data.length ? (
          <Empty description="catalogEmpty" />
        ) : (
          <div className="table-scroll" role="region" aria-label={t('catalog')} tabIndex={0}>
            <table>
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
                    <td>
                      <code>{item.marker_code}</code>
                    </td>
                    <td>{item.name}</td>
                    <td>{item.canonical_unit}</td>
                    <td>
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
