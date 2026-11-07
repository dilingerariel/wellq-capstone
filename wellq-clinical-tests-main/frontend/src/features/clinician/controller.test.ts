import { it, expect, vi, describe } from 'vitest'
import { ClinicianController } from './controller'
import { documentSchema, proposalSchema, bodyFor, createDraft, type ClinicianApi } from './model'
import { ApiError } from '../../services/http'
function setup() {
  let doc = documentSchema.parse({
      clinical_test_id: 'synthetic-doc',
      patient_id: 'synthetic-patient',
      title: 'Synthetic clinical document',
      test_type: 'blood_test',
      test_date: '2026-01-01',
      file: { name: 'synthetic.pdf', mime_type: 'application/pdf', size_bytes: 1 },
      status: 'ready_for_review',
      review: { status: 'not_reviewed' },
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    }),
    ext = proposalSchema.parse({
      clinical_test_id: 'synthetic-doc',
      extraction_id: 'synthetic-extraction',
      status: 'confirmed',
      document: {},
      panels: [
        {
          panel_code: 'metabolic',
          panel_name_raw: 'Synthetic panel',
          markers: [
            {
              marker_code: 'glucose',
              raw_name: 'Synthetic glucose',
              value_raw: '95',
              unit_raw: 'mg/dL',
            },
          ],
        },
      ],
    })
  let allowed = true,
    permissions = ['clinical:review', 'extractions:validate']
  const api: ClinicianApi = {
    document: vi.fn(async () => structuredClone(doc)),
    extraction: vi.fn(async () => structuredClone(ext)),
    review: vi.fn(async () => {
      doc = { ...doc, review: { status: 'reviewed', reviewed_by: 'synthetic-clinician' } }
      return structuredClone(doc)
    }),
    validate: vi.fn(async (_id, b) => {
      ext = {
        ...ext,
        status: b.validation_status === 'rejected' ? 'rejected' : 'clinically_validated',
      }
      return structuredClone(ext)
    }),
  }
  const invalidate = vi.fn(),
    c = new ClinicianController(
      api,
      () => ({ allowed, permissions, clinician: 'synthetic-clinician' }),
      async () => true,
      invalidate,
    )
  return {
    c,
    api,
    invalidate,
    getDoc: () => doc,
    setDoc: (v: typeof doc) => {
      doc = v
    },
    getExt: () => ext,
    setExt: (v: typeof ext) => {
      ext = v
    },
    offline: () => {
      allowed = false
      c.suspend()
    },
    online: () => {
      allowed = true
    },
    revoke: () => {
      allowed = false
      c.clear()
    },
    noGrants: () => {
      permissions = []
    },
  }
}
async function start(c: ClinicianController) {
  await c.load('synthetic-doc', 'synthetic-patient')
}
describe('clinical operations', () => {
  it('uses distinct note payloads and sends actual marker corrections', () => {
    const { getExt } = setup(),
      ext = getExt(),
      d = createDraft(ext)
    d.reviewNote = 'private review'
    d.clinicalNote = 'private validation'
    d.markers.glucose!.value = '96'
    d.markers.glucose!.reason = 'transcription'
    expect(bodyFor('review', d, ext)).toEqual({
      review_status: 'reviewed',
      review_note: 'private review',
    })
    expect(bodyFor('validated', d, ext)).toEqual({
      validation_status: 'validated',
      clinical_note: 'private validation',
      marker_corrections: [
        { marker_code: 'glucose', value_raw: '96', unit_raw: 'mg/dL', reason: 'transcription' },
      ],
    })
    expect(() => bodyFor('rejected', d, ext)).toThrow('clinicalRejectEdits')
  })
  it.each(['review', 'validated', 'rejected'] as const)(
    'single flight, explicit %s updates state and invalidates affected queries',
    async (action) => {
      const { c, api, invalidate } = setup()
      await start(c)
      c.preview(action)
      await Promise.all([c.send(), c.send()])
      expect(action === 'review' ? api.review : api.validate).toHaveBeenCalledTimes(1)
      expect(c.getSnapshot().phase).toBe('done')
      expect(invalidate).toHaveBeenCalledOnce()
    },
  )
  it('keeps corrections and the other note after a document review succeeds', async () => {
    const { c } = setup()
    await start(c)
    const d = c.getSnapshot().draft
    c.update({
      ...d,
      clinicalNote: 'unsent validation',
      markers: { glucose: { value: '96', unit: 'mg/dL', reason: '' } },
    })
    c.preview('review')
    await c.send()
    expect(c.getSnapshot().draft.clinicalNote).toBe('unsent validation')
    expect(c.getSnapshot().draft.markers.glucose!.value).toBe('96')
    await start(c)
    expect(c.getSnapshot().phase).toBe('editing')
  })
  it('review retry uses unchanged body after ambiguous receipt, same reviewer only', async () => {
    const { c, api, getDoc, setDoc } = setup()
    await start(c)
    c.update({ ...c.getSnapshot().draft, reviewNote: 'same private note' })
    c.preview('review')
    vi.mocked(api.review).mockImplementationOnce(async () => {
      setDoc({ ...getDoc(), review: { status: 'reviewed', reviewed_by: 'synthetic-clinician' } })
      throw new ApiError(0, 'REQUEST_TIMEOUT')
    })
    await c.send()
    expect(c.getSnapshot().phase).toBe('uncertain')
    await c.reconcile()
    expect(c.getSnapshot().phase).toBe('done')
    expect(vi.mocked(api.review).mock.calls[0]![1]).toEqual(vi.mocked(api.review).mock.calls[1]![1])
  })
  it('never resends uncertain validation; reconciles without attributing success', async () => {
    const { c, api, getExt, setExt } = setup()
    await start(c)
    c.preview('validated')
    vi.mocked(api.validate).mockImplementationOnce(async () => {
      setExt({ ...getExt(), status: 'clinically_validated' })
      throw new ApiError(0, 'REQUEST_TIMEOUT')
    })
    await c.send()
    await c.send()
    await c.reconcile()
    expect(api.validate).toHaveBeenCalledTimes(1)
    expect(c.getSnapshot().phase).toBe('conflict')
    expect(c.getSnapshot().error).toBe('clinicalUncertain')
  })
  it('blocks another reviewer and superseded or concurrently modified extraction', async () => {
    const { c, api, getExt, setExt } = setup()
    await start(c)
    c.preview('validated')
    setExt({ ...getExt(), extraction_id: 'synthetic-new' })
    await c.send()
    expect(c.getSnapshot().phase).toBe('conflict')
    expect(api.validate).not.toHaveBeenCalled()
  })
  it('offline keeps private draft with no replay', async () => {
    const { c, api, offline, online } = setup()
    await start(c)
    c.update({ ...c.getSnapshot().draft, clinicalNote: 'RAM only' })
    offline()
    online()
    expect(api.validate).not.toHaveBeenCalled()
    expect(c.getSnapshot().draft.clinicalNote).toBe('RAM only')
  })
  it('patient boundary clears notes and ignores a late clinical reply', async () => {
    const { c, api } = setup()
    await start(c)
    c.update({ ...c.getSnapshot().draft, clinicalNote: 'private' })
    c.preview('validated')
    let reply!: (x: ReturnType<typeof proposalSchema.parse>) => void
    vi.mocked(api.validate).mockImplementationOnce(
      () =>
        new Promise((r) => {
          reply = r
        }),
    )
    const send = c.send()
    await vi.waitFor(() => expect(reply).toBeDefined())
    c.clear()
    reply(
      proposalSchema.parse({
        clinical_test_id: 'synthetic-doc',
        extraction_id: 'synthetic-extraction',
        status: 'clinically_validated',
        document: {},
      }),
    )
    await send
    expect(c.getSnapshot().id).toBe('')
    expect(c.getSnapshot().draft.clinicalNote).toBe('')
  })
  it('blocks missing permissions even when controller method is called', async () => {
    const { c, api, noGrants } = setup()
    await start(c)
    noGrants()
    c.preview('validated')
    await c.send()
    expect(api.validate).not.toHaveBeenCalled()
  })
  it.each([401, 403, 404, 409, 422, 429, 503])(
    'handles HTTP %s without automatic writes',
    async (status) => {
      const { c, api } = setup()
      await start(c)
      c.preview('validated')
      vi.mocked(api.validate).mockRejectedValueOnce(
        new ApiError(status, 'REQUEST_FAILED', status === 429 ? '60' : null),
      )
      await c.send()
      expect(api.validate).toHaveBeenCalledTimes(1)
      expect(c.getSnapshot().phase).not.toBe('done')
      if (status === 429) {
        c.preview('validated')
        await c.send()
        expect(api.validate).toHaveBeenCalledTimes(1)
      }
    },
  )
  it('only document review is available when extraction is hidden or pending', async () => {
    const { c, api } = setup()
    vi.mocked(api.extraction).mockRejectedValue(new ApiError(409, 'EXTRACTION_NOT_READY'))
    await start(c)
    expect(c.getSnapshot().extractionUnavailable).toBe(true)
    c.preview('validated')
    await c.send()
    expect(api.validate).not.toHaveBeenCalled()
    c.preview('review')
    await c.send()
    expect(api.review).toHaveBeenCalledTimes(1)
  })
})
