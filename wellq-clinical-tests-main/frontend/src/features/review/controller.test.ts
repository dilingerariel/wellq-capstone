import { describe, it, expect, vi } from 'vitest'
import { ReviewController } from './controller'
import { draftFor, extractionSchema, payloadFor, type ReviewApi } from './model'
import { ApiError } from '../../services/http'
import type { Exam } from '../../types/clinical'
export const proposal = () =>
  extractionSchema.parse({
    clinical_test_id: 'synthetic-doc',
    extraction_id: 'synthetic-extraction',
    status: 'awaiting_confirmation',
    document: { collection_date: '2026-01-01' },
    panels: [
      {
        panel_code: 'chemistry',
        panel_name_raw: 'Synthetic panel',
        markers: [
          {
            marker_code: 'glucose',
            raw_name: 'Synthetic glucose',
            value_raw: '90',
            unit_raw: 'mg/dL',
          },
        ],
      },
    ],
    flags: [],
  })
function setup() {
  let ext = proposal(),
    allowed = true
  const doc = {
    clinical_test_id: 'synthetic-doc',
    patient_id: 'synthetic-patient',
    status: 'ready_for_review',
    updated_at: '2026-01-01',
  } as Exam
  const api: ReviewApi = {
    document: vi.fn(async () => structuredClone(doc)),
    extraction: vi.fn(async () => structuredClone(ext)),
    confirm: vi.fn(async (_id, body) => {
      ext = { ...ext, status: 'confirmed' }
      expect(body.marker_edits?.[0]?.value_raw).toBe('95')
      return structuredClone(ext)
    }),
  }
  const c = new ReviewController(
    api,
    () => ({ patient: 'synthetic-patient', allowed, confirm: true }),
    async () => true,
  )
  return {
    c,
    api,
    doc,
    setExt: (x: typeof ext) => {
      ext = x
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
async function edit(c: ReviewController) {
  await c.load('synthetic-doc')
  const d = c.getSnapshot().draft!
  c.update({ ...d, markers: { glucose: { value: '95', unit: 'mg/dL' } } })
  c.review()
}
describe('review contract and continuity', () => {
  it.each(['extraction_failed', 'unreadable', 'not_applicable', 'discarded'] as const)(
    'does not confirm unavailable proposal state %s',
    async (status) => {
      const { c, api, setExt } = setup()
      setExt({ ...proposal(), status })
      await c.load('synthetic-doc')
      c.review()
      await c.confirm()
      expect(api.confirm).not.toHaveBeenCalled()
    },
  )
  it('pending extraction never enables confirmation or invents a proposal', async () => {
    const { c, api } = setup()
    vi.mocked(api.extraction).mockRejectedValueOnce(new ApiError(409, 'EXTRACTION_NOT_READY'))
    await c.load('synthetic-doc')
    expect(c.getSnapshot().extraction).toBeUndefined()
    expect(c.getSnapshot().error).toBe('EXTRACTION_NOT_READY')
    await c.confirm()
    expect(api.confirm).not.toHaveBeenCalled()
  })
  it('blocks ambiguous duplicate marker codes without merging clinical data', () => {
    const ext = proposal()
    ext.panels[0]!.markers.push({ ...ext.panels[0]!.markers[0]!, value_raw: '91' })
    expect(() => payloadFor(ext, draftFor(ext))).toThrow('reviewDuplicate')
  })
  it('encodes actual dates, identity, acknowledgments and changed markers', () => {
    const ext = proposal()
    ext.flags = [
      { code: 'identity_unverified' },
      { code: 'low_confidence', marker_code: 'glucose' },
    ]
    const d = draftFor(ext)
    expect(() => payloadFor(ext, d)).toThrow('reviewAcknowledgments')
    d.identity = true
    d.acknowledged = ['glucose']
    d.collection_date = '2026-01-02'
    d.markers.glucose!.value = '95'
    const body = payloadFor(ext, d)
    expect(body).toMatchObject({
      action: 'confirm',
      extraction_id: ext.extraction_id,
      document_edits: { identity_confirmed: true, collection_date: '2026-01-02' },
      marker_edits: [{ op: 'update', marker_code: 'glucose', value_raw: '95', unit_raw: 'mg/dL' }],
      acknowledged_marker_codes: ['glucose'],
    })
  })
  it('rejects removed/invalid/future dates and incomplete corrections', () => {
    const ext = proposal(),
      d = draftFor(ext)
    for (const value of ['', '2026-02-30', '2999-01-01']) {
      d.collection_date = value
      expect(() => payloadFor(ext, d)).toThrow('reviewInvalid')
    }
    d.collection_date = '2026-01-01'
    d.markers.glucose!.unit = ''
    expect(() => payloadFor(ext, d)).toThrow('reviewInvalid')
  })
  it('revalidates and sends exactly one corrected confirmation on double click', async () => {
    const { c, api } = setup()
    await edit(c)
    await Promise.all([c.confirm(), c.confirm()])
    expect(api.confirm).toHaveBeenCalledTimes(1)
    expect(c.getSnapshot().phase).toBe('done')
  })
  it('retains draft offline with no replay and checks version before retry', async () => {
    const { c, api, offline, online, setExt } = setup()
    await edit(c)
    offline()
    await c.confirm()
    expect(api.confirm).not.toHaveBeenCalled()
    expect(c.getSnapshot().draft!.markers.glucose!.value).toBe('95')
    online()
    setExt({ ...proposal(), extraction_id: 'replacement' })
    c.review()
    await c.confirm()
    expect(c.getSnapshot().phase).toBe('conflict')
    expect(api.confirm).not.toHaveBeenCalled()
  })
  it('replays a frozen request/key after lost confirmation response', async () => {
    const { c, api, setExt } = setup()
    await edit(c)
    vi.mocked(api.confirm).mockImplementationOnce(async () => {
      setExt({ ...proposal(), status: 'confirmed' })
      throw new ApiError(0, 'REQUEST_TIMEOUT')
    })
    await c.confirm()
    expect(c.getSnapshot().phase).toBe('uncertain')
    await c.confirm()
    expect(api.confirm).toHaveBeenCalledTimes(2)
    expect(vi.mocked(api.confirm).mock.calls[0]!.slice(1, 3)).toEqual(
      vi.mocked(api.confirm).mock.calls[1]!.slice(1, 3),
    )
    expect(c.getSnapshot().phase).toBe('done')
  })
  it('clears private drafts and ignores late results after session change', async () => {
    const { c, api } = setup()
    await edit(c)
    let resolve!: (x: ReturnType<typeof proposal>) => void
    vi.mocked(api.extraction).mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolve = r
        }),
    )
    const p = c.confirm()
    await vi.waitFor(() => expect(resolve).toBeDefined())
    c.clear()
    resolve(proposal())
    await p
    expect(c.getSnapshot().id).toBe('')
    expect(api.confirm).not.toHaveBeenCalled()
  })
  it.each([401, 403, 404, 409, 422, 429, 500, 503])(
    'retains safe state after HTTP %s without automatic resend',
    async (status) => {
      const { c, api } = setup()
      await edit(c)
      vi.mocked(api.confirm).mockRejectedValueOnce(
        new ApiError(status, 'REQUEST_FAILED', status === 429 ? '60' : null),
      )
      await c.confirm()
      expect(api.confirm).toHaveBeenCalledTimes(1)
      expect(c.getSnapshot().phase).toBe(
        status === 409 ? 'conflict' : status === 422 ? 'editing' : 'uncertain',
      )
      if (status === 429) {
        await c.confirm()
        expect(api.confirm).toHaveBeenCalledTimes(1)
      }
    },
  )
  it('detects same-extraction server changes without overwriting draft', async () => {
    const { c, api, setExt } = setup()
    await edit(c)
    const ext = proposal()
    ext.panels[0]!.markers[0]!.value_raw = '92'
    setExt(ext)
    await c.confirm()
    expect(c.getSnapshot().phase).toBe('conflict')
    expect(c.getSnapshot().draft!.markers.glucose!.value).toBe('95')
    expect(api.confirm).not.toHaveBeenCalled()
  })
})
