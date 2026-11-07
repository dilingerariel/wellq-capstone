import { expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ApiError, createHttp } from '../../services/http'
import { syntheticReport, syntheticSeries, syntheticScores } from '../../test/records'
import {
  exportSchema,
  authorizedReportScore,
  fingerprint,
  readPdf,
  reportParams,
  reportSchema,
  reportingApi,
  seriesSchema,
  scoresSchema,
  validDownload,
  type ReportingApi,
} from './model'
import { ReportExportController } from './export-controller'
import { constantRange, ordered, verifiedRange } from './TrendChart'
import { ScorePanel } from './ScorePanel'

function setup() {
  let exports = 0
  let current = reportSchema.parse(syntheticReport()),
    allowed = true
  const result = exportSchema.parse({
    export_id: 'synthetic-export',
    patient_id: 'synthetic-patient',
    status: 'ready',
    file_name: 'synthetic.pdf',
    download_url: 'https://storage.invalid/temporary-pdf',
    expires_at: new Date(Date.now() + 300000).toISOString(),
    size_bytes: 8,
    sha256: 'a'.repeat(64),
    storage: 'gcs',
    replayed: false,
    generated_at: '2026-11-01T12:00:00Z',
  })
  const api = {
    report: vi.fn(async () => structuredClone(current)),
    markers: vi.fn(),
    scores: vi.fn(),
    export: vi.fn<ReportingApi['export']>(async () => {
      result.replayed = ++exports > 1
      return result
    }),
  }
  const save = vi.fn(),
    read = vi.fn(async () => new Uint8Array([1, 2])),
    verify = vi.fn(async () => true)
  const c = new ReportExportController(api, () => allowed, verify, read, save)
  return {
    c,
    api,
    result,
    save,
    read,
    verify,
    report: current,
    setReport: (x: typeof current) => {
      current = x
    },
    revoke: () => {
      allowed = false
      c.clear()
    },
    offline: () => {
      allowed = false
      c.suspend()
    },
    online: () => {
      allowed = true
    },
  }
}
it('sorts actual observations, preserves zero and gaps, and only accepts coherent verified references', () => {
  const rows = seriesSchema.parse(syntheticSeries()).series[0]!.points
  expect(ordered([...rows].reverse()).map((p) => p.value)).toEqual([95, 98, null])
  expect(constantRange(rows, 'mg/dL', false)?.low).toBe(70)
  expect(
    verifiedRange({ ...rows[0]!, reference: { ...rows[0]!.reference, source: 'catalog' } }, false),
  ).toBe(false)
  expect(
    verifiedRange(
      { ...rows[0]!, reference: { low: 70, high: 110, unit: 'other', source: 'document' } },
      true,
    ),
  ).toBe(false)
  expect(constantRange([rows[0]!, { ...rows[1]!, reference: null }], 'mg/dL', true)).toBeNull()
})
it('shows authorized zero scores and suppresses unapproved values without inventing zero for null', () => {
  const { unmount } = render(<ScorePanel data={scoresSchema.parse(syntheticScores())} />)
  expect(screen.getAllByText('0').length).toBeGreaterThan(0)
  expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  unmount()
  render(<ScorePanel data={scoresSchema.parse(syntheticScores(false))} />)
  expect(screen.queryAllByText('0')).toHaveLength(0)
})
it('requires a matching approved snapshot before displaying a report score, including zero', () => {
  const scores = scoresSchema.parse(syntheticScores())
  const report = reportSchema.parse({ ...syntheticReport(), score: scores.current_snapshot })
  expect(authorizedReportScore(report, scores)).toBe(0)
  expect(authorizedReportScore(report)).toBeNull()
  expect(authorizedReportScore(report, scoresSchema.parse(syntheticScores(false)))).toBeNull()
  expect(
    authorizedReportScore(
      { ...report, score: { ...report.score!, snapshot_id: 'obsolete' } },
      scores,
    ),
  ).toBeNull()
})
it('keeps a stable report fingerprint across generation timestamps and strips private notes', () => {
  const a = reportSchema.parse({ ...syntheticReport(), review_note: 'PRIVATE TEST SENTINEL' })
  expect(fingerprint(a)).toBe(fingerprint({ ...a, generated_at: 'different' }))
  expect(JSON.stringify(a)).not.toContain('PRIVATE TEST SENTINEL')
})
it('invalidates the report fingerprint when extraction provenance changes without changed values', () => {
  const a = reportSchema.parse(syntheticReport())
  const b = reportSchema.parse({
    ...a,
    traceability: {
      ...a.traceability,
      extractions: [
        { clinical_test_id: 'synthetic-exam', extraction_id: 'replacement', status: 'confirmed' },
      ],
    },
  })
  expect(fingerprint(a)).not.toBe(fingerprint(b))
})
it('single flight generates once and downloads only after an explicit action and fresh checks', async () => {
  const { c, api, report, save, read } = setup()
  await Promise.all([
    c.prepare('synthetic-patient', reportParams, report),
    c.prepare('synthetic-patient', reportParams, report),
  ])
  expect(api.export).toHaveBeenCalledOnce()
  expect(read).not.toHaveBeenCalled()
  await Promise.all([c.download(), c.download()])
  expect(read).toHaveBeenCalledOnce()
  expect(save).toHaveBeenCalledOnce()
  expect(api.export).toHaveBeenCalledTimes(2)
  expect(api.export.mock.calls[0]?.[2]).toBe(api.export.mock.calls[1]?.[2])
  expect(c.getSnapshot().phase).toBe('downloaded')
})
it('retains the exact idempotency key after timeout and pending signer; never retries automatically', async () => {
  const { c, api, report, result } = setup()
  api.export.mockRejectedValueOnce(new ApiError(0, 'REQUEST_TIMEOUT'))
  await c.prepare('synthetic-patient', reportParams, report)
  expect(c.getSnapshot().phase).toBe('uncertain')
  expect(api.export).toHaveBeenCalledOnce()
  api.export.mockResolvedValueOnce({
    ...result,
    status: 'download_pending',
    download_url: null,
    expires_at: null,
  })
  await c.prepare('synthetic-patient', reportParams, report)
  expect(c.getSnapshot().phase).toBe('pending')
  await c.prepare('synthetic-patient', reportParams, report)
  expect(new Set(api.export.mock.calls.map((args) => args[2])).size).toBe(1)
})
it('blocks stale source before generation, after generation and before downloading', async () => {
  for (const stage of ['before', 'after', 'download']) {
    const { c, api, report, setReport, read } = setup()
    const changed = { ...report, flags: [{ code: 'synthetic-change', severity: 'info' }] }
    if (stage === 'before') setReport(changed)
    if (stage === 'after')
      api.export.mockImplementationOnce(async () => {
        setReport(changed)
        return setup().result
      })
    await c.prepare('synthetic-patient', reportParams, report)
    if (stage === 'download') {
      setReport(changed)
      await c.download()
    }
    expect(c.getSnapshot().phase).toBe('stale')
    expect(read).not.toHaveBeenCalled()
    if (stage === 'before') expect(api.export).not.toHaveBeenCalled()
  }
})
it('rejects a PDF created from an intervening source even when the visible report returns to its original state', async () => {
  const { c, api, report, result, read, save } = setup()
  // A -> B during generation -> A before both client reads. The backend's
  // persisted full-source hash still binds this PDF to B and rejects replay.
  api.export
    .mockResolvedValueOnce(result)
    .mockRejectedValue(new ApiError(409, 'EXPORT_SOURCE_CHANGED'))
  await c.prepare('synthetic-patient', reportParams, report)
  await c.download()
  expect(read).toHaveBeenCalledOnce()
  expect(save).not.toHaveBeenCalled()
  expect(c.getSnapshot().phase).toBe('stale')
})
it('discards verified bytes when the source changes while storage is responding', async () => {
  const { c, api, report, read, save } = setup()
  await c.prepare('synthetic-patient', reportParams, report)
  read.mockImplementationOnce(async () => {
    api.export.mockRejectedValue(new ApiError(409, 'EXPORT_SOURCE_CHANGED'))
    return new Uint8Array([1, 2])
  })
  await c.download()
  expect(save).not.toHaveBeenCalled()
  expect(c.getSnapshot().phase).toBe('stale')
})
it('expires private links and renews them with the existing key', async () => {
  const { c, api, result, report, read } = setup()
  await c.prepare('synthetic-patient', reportParams, report)
  result.expires_at = new Date(Date.now() - 1000).toISOString()
  await c.download()
  expect(read).not.toHaveBeenCalled()
  expect(c.getSnapshot().phase).toBe('pending')
  result.expires_at = new Date(Date.now() + 300000).toISOString()
  await c.prepare('synthetic-patient', reportParams, report)
  expect(api.export.mock.calls[0]?.[2]).toBe(api.export.mock.calls[1]?.[2])
})
it.each(['export_id', 'sha256', 'size_bytes', 'replayed'] as const)(
  'rejects changed export proof %s before saving any bytes',
  async (field) => {
    const { c, api, report, result, save } = setup()
    await c.prepare('synthetic-patient', reportParams, report)
    const changed = {
      ...result,
      replayed: true,
      [field]: field === 'replayed' ? false : field === 'size_bytes' ? 99 : 'different',
    }
    api.export.mockResolvedValueOnce(changed)
    await c.download()
    expect(save).not.toHaveBeenCalled()
    expect(c.getSnapshot().phase).toBe('stale')
  },
)
it('clears data and ignores delayed export replies on identity/patient cancellation', async () => {
  const { c, api, report, result, revoke } = setup()
  let resolve!: (v: typeof result) => void
  api.export.mockImplementationOnce(
    () =>
      new Promise((r) => {
        resolve = r
      }),
  )
  const task = c.prepare('synthetic-patient', reportParams, report)
  await vi.waitFor(() => expect(resolve).toBeDefined())
  revoke()
  resolve(result)
  await task
  expect(c.getSnapshot().result).toBeUndefined()
  expect(c.getSnapshot().patient).toBe('')
})
it('keeps an uncertain plan offline without automatic mutation replay or download', async () => {
  const { c, api, report, offline, online, read } = setup()
  await c.prepare('synthetic-patient', reportParams, report)
  offline()
  await c.download()
  online()
  expect(api.export).toHaveBeenCalledOnce()
  expect(read).not.toHaveBeenCalled()
})
it('rejects unsafe URLs, null ready links, forged patients and unverified PDF bytes', async () => {
  const { result } = setup()
  expect(() => exportSchema.parse({ ...result, download_url: null })).toThrow()
  expect(() => validDownload({ ...result, download_url: 'http://storage.invalid/file' })).toThrow()
  expect(() => validDownload({ ...result, download_url: 'javascript:void(0)' })).toThrow()
  const fetcher = vi.fn<typeof fetch>(
    async () => new Response('%PDF-X', { headers: { 'Content-Type': 'application/pdf' } }),
  )
  vi.stubGlobal('fetch', fetcher)
  await expect(readPdf(result, new AbortController().signal)).rejects.toBeDefined()
  const options = fetcher.mock.calls[0]?.[1] as RequestInit
  expect(options.credentials).toBe('omit')
  expect(options.cache).toBe('no-store')
  expect(options.redirect).toBe('error')
  expect(options.headers).not.toHaveProperty('Authorization')
  vi.unstubAllGlobals()
  const api = reportingApi(
    createHttp(
      '/api/v1',
      () => undefined,
      () => {},
    ),
  )
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(JSON.stringify(syntheticReport('synthetic-other-patient')), { status: 200 }),
    ),
  )
  await expect(api.report('synthetic-patient', reportParams)).rejects.toMatchObject({ status: 403 })
  vi.unstubAllGlobals()
})
it.each([403, 404, 409, 422, 429, 502, 503])(
  'handles export HTTP %s without automatic retries',
  async (status) => {
    const { c, api, report } = setup()
    api.export.mockRejectedValueOnce(
      new ApiError(status, 'REQUEST_FAILED', status === 429 ? '60' : null),
    )
    await c.prepare('synthetic-patient', reportParams, report)
    expect(c.getSnapshot().phase).not.toBe('ready')
    expect(api.export).toHaveBeenCalledOnce()
    if (status === 429) {
      await c.prepare('synthetic-patient', reportParams, report)
      expect(api.export).toHaveBeenCalledOnce()
    }
  },
)
