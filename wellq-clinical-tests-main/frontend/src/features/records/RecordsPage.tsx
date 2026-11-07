import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { NavLink, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { RefreshCw, Download, TrendingUp, FileText } from 'lucide-react'
import { useRuntime } from '../../app/runtime'
import { usePatientScope } from '../exams/PatientScope'
import { CachedNotice, NeedsConnection } from '../../components/Continuity'
import { Empty, ErrorState, Loading } from '../../components/States'
import { ApiError } from '../../services/http'
import { ordered, TrendChart } from './TrendChart'
import { ScorePanel } from './ScorePanel'
import { authorizedReportScore, reportParams } from './model'
import '../../styles/records.css'

export function RecordsPage({ view }: { view: 'history' | 'report' }) {
  const { mode, session, boundary } = useRuntime(),
    { patientId } = usePatientScope(),
    { t } = useTranslation()
  if (mode !== 'api')
    return (
      <section className="panel state">
        <h1>{t('recordsTitle')}</h1>
        <p>{t('recordsDemo')}</p>
      </section>
    )
  if (!session?.permissions.includes('clinical:read')) return <Empty description="noGrant" />
  if (!patientId) return <Empty description="noPatient" />
  return (
    <Records
      key={`${boundary}:${session.tenantId}:${session.resourceId}:${patientId}`}
      patient={patientId}
      view={view}
    />
  )
}
function Records({ patient, view }: { patient: string; view: 'history' | 'report' }) {
  const { t, i18n } = useTranslation()
  const { reporting, reportExport, session, boundary, canRequest, verifySession, source } =
    useRuntime()
  const client = useQueryClient(),
    active = useRef(true)
  useEffect(() => {
    active.current = true
    return () => {
      active.current = false
    }
  }, [])
  const [denied, setDenied] = useState(false),
    [marker, setMarker] = useState(''),
    [dates, setDates] = useState({ from: '', to: '' })
  const [params, setParams] = useState(reportParams),
    [filterError, setFilterError] = useState(false)
  const [now, setNow] = useState(() => Date.now()),
    [refreshing, setRefreshing] = useState(false)
  const scope = useMemo(
    () => ['records', boundary, session!.tenantId, session!.resourceId, patient],
    [boundary, session, patient],
  )
  const report = useQuery({
    queryKey: [...scope, 'report', params],
    queryFn: ({ signal }) => reporting.report(patient, params, signal),
    enabled: canRequest && !denied,
  })
  const scores = useQuery({
    queryKey: [...scope, 'score'],
    queryFn: ({ signal }) => reporting.scores(patient, signal),
    enabled: canRequest && !denied,
  })
  const currentReport =
    report.error instanceof ApiError && report.error.status === 404 ? undefined : report.data
  const actualCodes = currentReport?.results.panels.flatMap((p) => p.rows) || []
  const effectiveMarker = marker || actualCodes[0]?.marker_code || ''
  const series = useQuery({
    queryKey: [...scope, 'markers', effectiveMarker, dates],
    queryFn: ({ signal }) =>
      reporting.markers(patient, effectiveMarker, dates.from, dates.to, signal),
    enabled: canRequest && !denied && !!effectiveMarker,
  })
  // Catalog is public clinical metadata but shares the private scope for boundary cleanup.
  const catalog = useQuery({
    queryKey: [...scope, 'catalog'],
    queryFn: ({ signal }) => source!.catalog(signal),
    enabled: canRequest && !denied,
  })
  const exported = useSyncExternalStore(reportExport.subscribe, reportExport.getSnapshot)
  useEffect(() => {
    const revoked =
      [report.error, scores.error, series.error, catalog.error].some(
        (e) => e instanceof ApiError && [401, 403].includes(e.status),
      ) ||
      exported.error === 'RECORD_PATIENT_MISMATCH' ||
      exported.error === 'reviewHttp403'
    if (revoked)
      queueMicrotask(() => {
        if (active.current) setDenied(true)
      })
  }, [report.error, scores.error, series.error, catalog.error, exported.error])
  useEffect(() => {
    if (denied) {
      reportExport.clear()
      void client.cancelQueries({ queryKey: scope })
      client.removeQueries({ queryKey: scope })
    }
  }, [denied, client, reportExport, scope])
  useEffect(() => {
    if (exported.phase !== 'ready' && exported.retryAt <= Date.now()) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [exported.phase, exported.retryAt])
  async function refresh() {
    if (!canRequest || refreshing) return
    setRefreshing(true)
    try {
      if (!(await verifySession()) || !active.current) return
      reportExport.clear()
      await Promise.all([
        report.refetch({ cancelRefetch: false }),
        scores.refetch({ cancelRefetch: false }),
        effectiveMarker ? series.refetch({ cancelRefetch: false }) : Promise.resolve(),
      ])
    } finally {
      if (active.current) setRefreshing(false)
    }
  }
  const codes = [
    ...new Map(
      [...(catalog.data || []), ...actualCodes].map((x) => [x.marker_code, x.name]),
    ).entries(),
  ]
  const points = ordered(series.data?.series[0]?.points || [])
  const busy = ['generating', 'downloading'].includes(exported.phase),
    canExport =
      canRequest &&
      !denied &&
      session?.permissions.includes('reports:export') &&
      session.capabilities.includes('report_export')
  const expires = exported.result?.expires_at ? Date.parse(exported.result.expires_at) : 0
  const number = (v: number | null | undefined) =>
    v == null ? '—' : new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 6 }).format(v)
  const revoked =
    [report.error, scores.error, series.error, catalog.error].some(
      (e) => e instanceof ApiError && [401, 403].includes(e.status),
    ) || ['RECORD_PATIENT_MISMATCH', 'reviewHttp403'].includes(exported.error || '')
  if (denied || revoked)
    return (
      <section className="panel state" role="alert">
        <h1>{t('recordsAccessDenied')}</h1>
        <p>{t('recordsAccessHelp')}</p>
      </section>
    )
  return (
    <div className="records-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('clinical')}</span>
          <h1>{t(view === 'history' ? 'recordsTitle' : 'recordsReportTitle')}</h1>
          <p>{t('recordsIntro')}</p>
        </div>
        <button
          className="button secondary"
          disabled={!canRequest || refreshing || busy}
          onClick={() => void refresh()}
        >
          <RefreshCw size={17} aria-hidden="true" />
          {t('recordsRefresh')}
        </button>
      </div>
      <nav className="records-tabs" aria-label={t('recordsNavigation')}>
        <NavLink to="/history">
          <TrendingUp size={18} aria-hidden="true" />
          {t('recordsHistoryNav')}
        </NavLink>
        <NavLink to="/reports">
          <FileText size={18} aria-hidden="true" />
          {t('recordsReportsNav')}
        </NavLink>
      </nav>
      <CachedNotice
        error={
          report.isError ||
          series.isError ||
          (scores.isError &&
            !(scores.error instanceof ApiError && scores.error.code === 'NO_SCORE_AVAILABLE'))
        }
      />
      <p className="small-note">
        {t('patientContext')}: {patient} · {t('recordsReadAt')}:{' '}
        {report.dataUpdatedAt ? new Date(report.dataUpdatedAt).toLocaleString(i18n.language) : '—'}
      </p>
      <div className="metric-grid records-metrics">
        <article className="metric">
          <span>{t('recordsReceivedMarkers')}</span>
          <strong>{currentReport ? actualCodes.length : '—'}</strong>
        </article>
        <article className="metric">
          <span>{t('recordsReceivedMeasurements')}</span>
          <strong>{series.data ? points.length : '—'}</strong>
        </article>
        <article className="metric">
          <span>{t('recordsCatalog')}</span>
          <strong className="records-version">
            {currentReport?.traceability.catalog_version || '—'}
          </strong>
        </article>
      </div>
      {view === 'history' && (
        <section className="panel records-section">
          <h2>{t('recordsTrends')}</h2>
          <form
            className="records-filters"
            onSubmit={(e) => {
              e.preventDefault()
              const form = new FormData(e.currentTarget),
                from = String(form.get('from') || ''),
                to = String(form.get('to') || '')
              if (from && to && from > to) {
                setFilterError(true)
                return
              }
              setFilterError(false)
              setDates({ from, to })
              setMarker(String(form.get('marker') || ''))
            }}
          >
            <label>
              {t('recordsMarker')}
              <select
                name="marker"
                key={effectiveMarker}
                defaultValue={effectiveMarker}
                disabled={!canRequest || !codes.length}
              >
                <option value="">{t('recordsChooseMarker')}</option>
                {codes.map(([code, name]) => (
                  <option key={code} value={code}>
                    {name} ({code})
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t('recordsFrom')}
              <input type="date" name="from" defaultValue={dates.from} />
            </label>
            <label>
              {t('recordsTo')}
              <input type="date" name="to" defaultValue={dates.to} />
            </label>
            <button className="button secondary" disabled={!canRequest || !codes.length}>
              {t('recordsApply')}
            </button>
          </form>
          {filterError && <p role="alert">{t('recordsInvalidDates')}</p>}
          <p className="small-note">{t('recordsCatalogHelp')}</p>
          {series.isError && (
            <ErrorState
              error={series.error}
              retry={canRequest ? () => void refresh() : undefined}
            />
          )}
          {!effectiveMarker ? (
            <Empty description="recordsChooseMarker" />
          ) : !series.data ? (
            series.isError ? null : canRequest ? (
              <Loading />
            ) : (
              <NeedsConnection />
            )
          ) : !points.length ? (
            <Empty description="recordsNoMeasurements" />
          ) : (
            <>
              <TrendChart
                key={effectiveMarker + JSON.stringify(dates)}
                points={points}
                name={codes.find(([code]) => code === effectiveMarker)?.[1] || effectiveMarker}
                approved={
                  catalog.data?.find((c) => c.marker_code === effectiveMarker)?.clinically_validated
                }
              />
              <div className="records-table-wrap">
                <table className="records-table">
                  <caption>{t('recordsMeasurementTable')}</caption>
                  <thead>
                    <tr>
                      {['Date', 'Value', 'Reference', 'Status', 'Origin'].map((k) => (
                        <th key={k} scope="col">
                          {t('records' + k)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {points.map((p, i) => (
                      <tr key={p.clinical_test_id + ':' + i}>
                        <td data-label={t('recordsDate')}>{p.measured_on}</td>
                        <td data-label={t('recordsValue')}>
                          {number(p.value)} {p.unit || '—'}
                        </td>
                        <td data-label={t('recordsReference')}>
                          {number(p.reference?.low)}–{number(p.reference?.high)}{' '}
                          {p.reference?.unit || ''}
                          <small>
                            {t('recordsSource_' + p.reference?.source, {
                              defaultValue: t('recordsUnknown'),
                            })}
                          </small>
                        </td>
                        <td data-label={t('recordsStatus')}>
                          {t('recordsStatus_' + p.status, { defaultValue: t('recordsUnknown') })}
                          <small>
                            {t(p.edited ? 'recordsEdited' : 'recordsUnedited')} ·{' '}
                            {t('recordsConfirmation_' + p.confirmation_level, {
                              defaultValue: t('recordsUnknown'),
                            })}
                          </small>
                        </td>
                        <td data-label={t('recordsOrigin')}>
                          <Link to={`/exams/${encodeURIComponent(p.clinical_test_id)}`}>
                            {p.clinical_test_id}
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}
      <section className="panel records-section">
        <h2>{t('recordsScores')}</h2>
        {scores.error instanceof ApiError && scores.error.code === 'NO_SCORE_AVAILABLE' ? (
          <p role="status">
            {t('recordsNoScore')} {t('recordsReason_' + scores.error.reason, { defaultValue: '' })}
          </p>
        ) : scores.isError ? (
          <>
            <ErrorState error={scores.error} />
            {scores.data && scores.error instanceof ApiError && scores.error.status >= 500 && (
              <ScorePanel data={scores.data} />
            )}
          </>
        ) : scores.data ? (
          <ScorePanel data={scores.data} />
        ) : canRequest ? (
          <Loading />
        ) : (
          <NeedsConnection />
        )}
        <p className="small-note">{t('recordsNotDiagnosis')}</p>
      </section>
      {view === 'report' && (
        <section className="panel records-section">
          <h2>{t('recordsReportTitle')}</h2>
          <form
            className="records-filters"
            onSubmit={(e) => {
              e.preventDefault()
              if (busy || !canRequest) return
              const data = new FormData(e.currentTarget),
                months = Number(data.get('months')),
                exam = String(data.get('exam') || '').trim()
              if (!Number.isInteger(months) || months < 1 || months > 60) return
              reportExport.clear()
              setParams({
                window_months: months,
                include_series: true,
                clinical_test_id: exam || null,
              })
            }}
          >
            <label>
              {t('recordsMonths')}
              <input
                type="number"
                name="months"
                min={1}
                max={60}
                required
                defaultValue={params.window_months}
                disabled={busy}
              />
            </label>
            <label>
              {t('recordsExamOptional')}
              <input
                name="exam"
                autoComplete="off"
                maxLength={200}
                defaultValue={params.clinical_test_id || ''}
                disabled={busy}
              />
            </label>
            <button className="button secondary" disabled={!canRequest || busy}>
              {t('recordsApplyReport')}
            </button>
          </form>
          {report.isError && (
            <ErrorState
              error={report.error}
              retry={canRequest ? () => void refresh() : undefined}
            />
          )}
          {!currentReport ? (
            report.isError ? null : canRequest ? (
              <Loading />
            ) : (
              <NeedsConnection />
            )
          ) : (
            <>
              <p>
                {t('recordsGenerated')}: <time>{currentReport.generated_at}</time> ·{' '}
                {t('recordsMode_' + currentReport.header.mode)}
              </p>
              <p>
                {currentReport.header.window.from} — {currentReport.header.window.to}
              </p>
              <p>
                {t('recordsReportScore')}:{' '}
                {authorizedReportScore(currentReport, scores.isError ? undefined : scores.data) ==
                null
                  ? t('recordsNoScore')
                  : number(authorizedReportScore(currentReport, scores.data))}
              </p>
              {currentReport.header.exams.map((exam) => (
                <article className="records-exam" key={exam.clinical_test_id}>
                  <strong>{exam.title || exam.clinical_test_id}</strong>
                  <p>
                    {exam.test_date || '—'} ·{' '}
                    {t('uploadExtraction_' + exam.validation_status, {
                      defaultValue: t('recordsUnknown'),
                    })}{' '}
                    · {t('review_' + exam.review_status, { defaultValue: t('recordsUnknown') })}
                  </p>
                </article>
              ))}
              {!actualCodes.length && <Empty description="recordsNoMeasurements" />}
              {currentReport.results.panels.map((panel, index) => (
                <div key={panel.panel_code || index}>
                  <h3>{panel.panel_code || t('recordsUnknown')}</h3>
                  <div className="records-table-wrap">
                    <table className="records-table">
                      <caption>{t('recordsReportResults')}</caption>
                      <thead>
                        <tr>
                          {['Marker', 'Value', 'Reference', 'Status', 'Origin'].map((k) => (
                            <th key={k} scope="col">
                              {t('records' + k)}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {panel.rows.map((row) => (
                          <tr key={row.marker_code}>
                            <td data-label={t('recordsMarker')}>
                              {row.name}
                              <small>{row.marker_code}</small>
                            </td>
                            <td data-label={t('recordsValue')}>
                              {row.censoring === 'left'
                                ? '≤ '
                                : row.censoring === 'right'
                                  ? '≥ '
                                  : ''}
                              {number(row.value)} {row.unit || '—'}
                              <small>
                                {t('recordsOriginal')}: {row.original.value_raw ?? '—'}{' '}
                                {row.original.unit_raw || ''}
                              </small>
                            </td>
                            <td data-label={t('recordsReference')}>
                              {number(row.reference.low)}–{number(row.reference.high)}{' '}
                              {row.reference.unit || ''}
                              <small>
                                {t('recordsSource_' + row.reference.source, {
                                  defaultValue: t('recordsUnknown'),
                                })}
                              </small>
                            </td>
                            <td data-label={t('recordsStatus')}>
                              {t('recordsStatus_' + row.status, {
                                defaultValue: t('recordsUnknown'),
                              })}
                              <small>
                                {row.subscore_blank_reason
                                  ? t('recordsReason_' + row.subscore_blank_reason, {
                                      defaultValue: row.subscore_blank_reason,
                                    })
                                  : ''}
                              </small>
                            </td>
                            <td data-label={t('recordsOrigin')}>
                              {row.origin.measured_on || '—'}
                              <small>
                                <Link
                                  to={`/exams/${encodeURIComponent(row.origin.clinical_test_id)}`}
                                >
                                  {row.origin.clinical_test_id}
                                </Link>
                              </small>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
              {currentReport.flags.length > 0 && (
                <ul>
                  {currentReport.flags.map((f, i) => (
                    <li key={i}>
                      {f.severity} · {f.code} · {f.message || ''}
                    </li>
                  ))}
                </ul>
              )}
              {currentReport.traceability.excluded_markers.length > 0 && (
                <details>
                  <summary>{t('recordsExcluded')}</summary>
                  <ul>
                    {currentReport.traceability.excluded_markers.map((m, i) => (
                      <li key={i}>
                        {m.marker_code || m.raw_name || '—'} ·{' '}
                        {t('recordsReason_' + m.reason, { defaultValue: m.reason })}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              <p className="small-note">{t('recordsPrivateNotes')}</p>
              <section className="records-export" aria-label={t('recordsExportTitle')}>
                <h3>{t('recordsExportTitle')}</h3>
                <p>{t('recordsExportHelp')}</p>
                {!canExport && <p>{t('recordsExportPermission')}</p>}
                <div className="upload-actions">
                  <button
                    className="button primary"
                    disabled={
                      !canExport ||
                      busy ||
                      exported.phase === 'stale' ||
                      report.isError ||
                      report.isFetching ||
                      now < exported.retryAt
                    }
                    onClick={() => void reportExport.prepare(patient, params, currentReport!)}
                  >
                    <FileText size={17} aria-hidden="true" />
                    {t(
                      ['pending', 'uncertain'].includes(exported.phase) ||
                        (expires <= now && exported.phase === 'ready')
                        ? 'recordsRetryExport'
                        : 'recordsGeneratePdf',
                    )}
                  </button>
                  <button
                    className="button secondary"
                    disabled={!canExport || exported.phase !== 'ready' || expires <= now}
                    onClick={() => void reportExport.download()}
                  >
                    <Download size={17} aria-hidden="true" />
                    {t('recordsDownloadPdf')}
                  </button>
                </div>
                {exported.patient === patient && (
                  <>
                    <p role="status">{t('recordsExport_' + exported.phase)}</p>
                    {exported.error && (
                      <p role="alert">
                        {t(exported.error, { defaultValue: t('recordsExportError') })}
                      </p>
                    )}
                    {exported.phase === 'ready' && (
                      <p>
                        {t(expires <= now ? 'recordsUrlExpired' : 'recordsUrlExpires')}:{' '}
                        {exported.result?.expires_at}
                      </p>
                    )}
                  </>
                )}
              </section>
            </>
          )}
        </section>
      )}
    </div>
  )
}
