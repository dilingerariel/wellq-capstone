import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Point } from './model'

export function dateValue(value: string) {
  const time = Date.parse(value)
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value.slice(0, 10)
    ? time
    : null
}
export function ordered(points: Point[]) {
  return [...points].sort(
    (a, b) => (dateValue(a.measured_on) ?? Infinity) - (dateValue(b.measured_on) ?? Infinity),
  )
}
export function verifiedRange(p: Point, approved: boolean) {
  const r = p.reference
  return (
    !!r &&
    (r.source === 'document' || (r.source === 'catalog' && approved)) &&
    r.unit === p.unit &&
    r.low != null &&
    r.high != null &&
    Number.isFinite(r.low) &&
    Number.isFinite(r.high) &&
    r.low < r.high
  )
}
export function constantRange(points: Point[], unit: string, approved: boolean) {
  const rows = points.filter((p) => p.unit === unit),
    r = rows[0]?.reference
  return rows.length > 0 &&
    rows.every(
      (p) =>
        verifiedRange(p, approved) &&
        p.reference?.low === r?.low &&
        p.reference?.high === r?.high &&
        p.reference?.source === r?.source,
    )
    ? r
    : null
}
export function TrendChart({
  points,
  name,
  approved = false,
}: {
  points: Point[]
  name: string
  approved?: boolean
}) {
  const { t, i18n } = useTranslation()
  const rows = ordered(points),
    units = [
      ...new Set(
        rows
          .filter((p) => p.unit && p.value != null && dateValue(p.measured_on) !== null)
          .map((p) => p.unit!),
      ),
    ]
  const [selected, setSelected] = useState('')
  const chosen = rows[Number(selected)]
  const date = (time: number) =>
    new Intl.DateTimeFormat(i18n.language, {
      timeZone: 'UTC',
      month: 'short',
      day: 'numeric',
    }).format(time)
  return (
    <>
      <p className="small-note">{t('recordsChartHelp')}</p>
      {!units.length && <p role="status">{t('recordsNoNumeric')}</p>}
      {units.map((unit) => {
        const data = rows
          .filter((p) => dateValue(p.measured_on) !== null)
          .map((p) => ({
            time: dateValue(p.measured_on)!,
            value: p.unit === unit ? p.value : null,
          }))
        const count = data.filter((p) => p.value != null).length,
          range = constantRange(rows, unit, approved)
        return (
          <figure className="records-figure" key={unit}>
            <figcaption>
              {name} · {unit}{' '}
              <span className="small-note">{t('recordsObservations', { count })}</span>
            </figcaption>
            {count < 2 && <p role="status">{t('recordsOnePoint')}</p>}
            <div className="records-chart">
              <ResponsiveContainer width="100%" height={280} minWidth={0}>
                <LineChart
                  data={data}
                  accessibilityLayer
                  aria-label={`${name} (${unit}). ${t('recordsChartKeys')}`}
                  margin={{ top: 15, right: 15, left: 0, bottom: 10 }}
                >
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    type="number"
                    domain={['dataMin', 'dataMax']}
                    tickFormatter={date}
                    tick={{ fill: 'var(--muted)', fontSize: 11 }}
                    minTickGap={35}
                  />
                  <YAxis
                    width={56}
                    domain={['auto', 'auto']}
                    tick={{ fill: 'var(--muted)', fontSize: 11 }}
                  />
                  <Tooltip
                    labelFormatter={(label) => date(Number(label))}
                    formatter={(value) => [`${value} ${unit}`, name]}
                    contentStyle={{
                      background: 'var(--surface)',
                      color: 'var(--text)',
                      borderColor: 'var(--border)',
                      borderRadius: 8,
                    }}
                    isAnimationActive={false}
                  />
                  <Legend />
                  {range && (
                    <ReferenceArea
                      y1={range.low!}
                      y2={range.high!}
                      fill="var(--accent-soft)"
                      fillOpacity={0.6}
                      ifOverflow="extendDomain"
                    />
                  )}
                  <Line
                    type="linear"
                    dataKey="value"
                    name={`${name} (${unit})`}
                    stroke="var(--accent-text)"
                    strokeWidth={2}
                    dot={{ r: 4 }}
                    activeDot={{ r: 6 }}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                  {selected !== '' &&
                    chosen?.unit === unit &&
                    chosen.value != null &&
                    dateValue(chosen.measured_on) !== null && (
                      <ReferenceDot
                        x={dateValue(chosen.measured_on)!}
                        y={chosen.value}
                        r={7}
                        fill="var(--surface)"
                        stroke="var(--text)"
                      />
                    )}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="small-note">
              {range
                ? `${t('recordsVerifiedBand')}: ${range.low}–${range.high} ${unit} · ${t('recordsSource_' + range.source)}`
                : t('recordsReferencePerPoint')}
            </p>
          </figure>
        )
      })}
      {rows.length > 0 && (
        <div className="records-inspector">
          <label>
            {t('recordsInspect')}
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">{t('recordsChooseMeasurement')}</option>
              {rows.map((p, i) => (
                <option key={i} value={i}>
                  {p.measured_on} · {p.value ?? '—'} {p.unit ?? '—'} · {p.clinical_test_id}
                </option>
              ))}
            </select>
          </label>
          {selected !== '' && chosen && (
            <p role="status">
              {chosen.measured_on} · {chosen.value ?? '—'} {chosen.unit ?? '—'} ·{' '}
              {t('recordsOrigin')}: {chosen.clinical_test_id}
            </p>
          )}
        </div>
      )}
    </>
  )
}
