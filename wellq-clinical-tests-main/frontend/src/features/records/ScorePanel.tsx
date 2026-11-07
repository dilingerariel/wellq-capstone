import { useTranslation } from 'react-i18next'
import type { Scores } from './model'

export function ScorePanel({ data }: { data: Scores }) {
  const { t, i18n } = useTranslation()
  const s = data.current_snapshot
  const number = (v: number | null | undefined) =>
    v == null ? '—' : new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 2 }).format(v)
  const snapshots = [s, ...(data.history || [])]
  return (
    <>
      <p>
        {t('recordsComputed')}: <time>{s.computed_at}</time>
      </p>
      <p className="small-note">
        {t('recordsCatalog')}: {s.catalog_version} · {t('recordsFormula')}: {s.scoring_version}
      </p>
      {!s.catalog_clinically_approved && <p role="status">{t('recordsUnapproved')}</p>}
      <div className="records-score-grid">
        <article className="metric">
          <span>{t('recordsLabIndex')}</span>
          <strong>{s.catalog_clinically_approved ? number(s.lab_index) : '—'}</strong>
          <span>{s.lab_index == null ? t('recordsNoScore') : t('recordsServerScore')}</span>
        </article>
        {Object.entries(s.pillars).map(([key, p]) => (
          <article className="metric" key={key}>
            <span>{t('recordsPillar_' + key, { defaultValue: key })}</span>
            <strong>
              {s.catalog_clinically_approved && p.status === 'published' ? number(p.score) : '—'}
            </strong>
            <span>
              {t('recordsCoverage')}: {number(p.coverage * 100)}%
            </span>
            <span>
              {t('recordsConfidence')}:{' '}
              {t('recordsConfidence_' + p.confidence, { defaultValue: t('recordsUnknown') })}
            </span>
            <span>
              {p.status === 'published' ? t('recordsPublished') : t('recordsInsufficient')}
            </span>
          </article>
        ))}
      </div>
      <details>
        <summary>
          {t('recordsSnapshotHistory')} ({data.history?.length ?? 0})
        </summary>
        <ul className="records-snapshots">
          {snapshots.map((x) => (
            <li key={x.snapshot_id}>
              <time>{x.computed_at}</time> · {x.catalog_version} · {x.scoring_version} ·{' '}
              {t('recordsLabIndex')}: {x.catalog_clinically_approved ? number(x.lab_index) : '—'}
            </li>
          ))}
        </ul>
      </details>
    </>
  )
}
