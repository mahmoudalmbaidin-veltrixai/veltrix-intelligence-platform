import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  uploadRaw: vi.fn(),
  downloadWithMetadata: vi.fn(),
  eventStream: vi.fn(),
}))

vi.mock('@/shared/lib/apiClient', () => ({ apiClient: api }))

import { platformInfrastructure } from './platformInfrastructure'

describe('platformInfrastructure', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses live tenant-aware job and file APIs', async () => {
    api.get.mockResolvedValue({ items: [] })
    await platformInfrastructure.jobs({ status: 'running', limit: 20 })
    expect(api.get).toHaveBeenCalledWith('/api/v1/jobs', {
      query: { status: 'running', limit: 20 },
    })

    const file = new File(['region,revenue'], 'report.csv', { type: 'text/csv' })
    await platformInfrastructure.upload(file)
    expect(api.uploadRaw).toHaveBeenCalledWith('/api/v1/files', file, {
      headers: { 'Content-Type': 'text/csv', 'X-File-Name': 'report.csv' },
    })

    const firefoxFile = new File(['region,revenue'], 'firefox.csv', {
      type: 'application/octet-stream',
    })
    await platformInfrastructure.upload(firefoxFile)
    expect(api.uploadRaw).toHaveBeenLastCalledWith('/api/v1/files', firefoxFile, {
      headers: { 'Content-Type': 'text/csv', 'X-File-Name': 'firefox.csv' },
    })

    const legacyCsvMime = new File(['region,revenue'], 'legacy.csv', {
      type: 'application/vnd.ms-excel',
    })
    await platformInfrastructure.upload(legacyCsvMime)
    expect(api.uploadRaw).toHaveBeenLastCalledWith('/api/v1/files', legacyCsvMime, {
      headers: { 'Content-Type': 'text/csv', 'X-File-Name': 'legacy.csv' },
    })
  })

  it('passes resumable event metadata through the central client', () => {
    platformInfrastructure.events(['job.progress'], { lastEventId: '42-0' })
    expect(api.eventStream).toHaveBeenCalledWith('/api/v1/events/stream', {
      query: { types: ['job.progress'] },
      signal: undefined,
      headers: { 'Last-Event-ID': '42-0' },
    })
  })

  it('reconnects from the saved cursor and suppresses duplicate events', async () => {
    vi.useFakeTimers()
    sessionStorage.clear()
    let connection = 0
    api.eventStream.mockImplementation(() => {
      connection += 1
      if (connection === 1) {
        return (async function* () {
          yield { id: '10-0', type: 'job.progress', data: { percent: 50 } }
          throw new TypeError('connection lost')
        })()
      }
      return (async function* () {
        yield { id: '10-0', type: 'job.progress', data: { percent: 50 } }
        yield { id: '11-0', type: 'job.completed', data: { percent: 100 } }
      })()
    })
    const controller = new AbortController()
    const received: string[] = []
    const consume = (async () => {
      for await (const event of platformInfrastructure.resilientEvents([], {
        scope: 'organization:workspace',
        signal: controller.signal,
      })) {
        received.push(event.id)
        if (event.id === '11-0') controller.abort()
      }
    })()
    await vi.advanceTimersByTimeAsync(1_000)
    await consume
    expect(received).toEqual(['10-0', '11-0'])
    expect(api.eventStream).toHaveBeenLastCalledWith(
      '/api/v1/events/stream',
      expect.objectContaining({ headers: { 'Last-Event-ID': '10-0' } }),
    )
    vi.useRealTimers()
  })
})
