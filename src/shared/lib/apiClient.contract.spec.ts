import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient, cancelAllRequests, setRequestContextProvider, setUnauthorizedHandler } from './apiClient'
import { ApiError } from '@/shared/types/api'

function json(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json', ...init.headers },
    ...init,
  })
}

describe('central API client contracts', () => {
  beforeEach(() => {
    setUnauthorizedHandler(() => undefined)
    setRequestContextProvider(() => ({
      token: 'test-token',
      orgId: 'org_a',
      workspaceId: 'ws_a',
      locale: 'en-US',
      timezone: 'Asia/Riyadh',
    }))
  })
  afterEach(() => {
    document.cookie = 'vip_csrf_token=; Max-Age=0; Path=/'
    vi.restoreAllMocks()
  })

  it('sends context, auth, locale, timezone, accept, correlation and JSON headers', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ ok: true }))
    await apiClient.post('/resources', { name: 'A' })
    const [url, init] = fetchMock.mock.calls[0]
    const headers = init?.headers as Headers
    expect(url).toBe('/resources')
    expect(init?.method).toBe('POST')
    expect(init?.credentials).toBe('include')
    expect(init?.body).toBe(JSON.stringify({ name: 'A' }))
    expect(headers.get('Authorization')).toBe('Bearer test-token')
    expect(headers.get('X-Organization-Id')).toBe('org_a')
    expect(headers.get('X-Workspace-Id')).toBe('ws_a')
    expect(headers.get('X-Locale')).toBe('en-US')
    expect(headers.get('X-Timezone')).toBe('Asia/Riyadh')
    expect(headers.get('X-Correlation-Id')).toBeTruthy()
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Accept')).toBe('application/json')
  })

  it.each([
    ['get', 'GET'],
    ['post', 'POST'],
    ['put', 'PUT'],
    ['patch', 'PATCH'],
    ['delete', 'DELETE'],
  ] as const)('supports %s', async (method, expected) => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({}))
    if (method === 'get' || method === 'delete') await apiClient[method]('/resource')
    else await apiClient[method]('/resource', { value: 1 })
    expect(fetchMock.mock.calls[0][1]?.method).toBe(expected)
  })

  it('supports arrays and nested filter query parameters', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json([]))
    await apiClient.get('/items', { query: { tags: ['a', 'b'], filters: { status: 'active', owner: 2 } } })
    expect(String(fetchMock.mock.calls[0][0])).toContain('tags=a&tags=b')
    expect(decodeURIComponent(String(fetchMock.mock.calls[0][0]))).toContain('filters[status]=active')
  })

  it('handles empty and 204 responses', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response('', { status: 200 }))
    await expect(apiClient.delete('/resource')).resolves.toBeUndefined()
    await expect(apiClient.get('/empty')).resolves.toBeUndefined()
  })

  it('uploads multipart without forcing a content type', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ id: 'upload-1' }))
    const form = new FormData()
    form.set('file', new Blob(['x']), 'x.txt')
    await apiClient.upload('/uploads', form)
    const init = fetchMock.mock.calls[0][1]
    expect(init?.body).toBe(form)
    expect((init?.headers as Headers).has('Content-Type')).toBe(false)
  })

  it('sends the double-submit CSRF token on unsafe requests', async () => {
    document.cookie = 'vip_csrf_token=csrf-value; Path=/'
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ ok: true }))
    await apiClient.post('/protected', {})
    const headers = fetchMock.mock.calls[0][1]?.headers as Headers
    expect(headers.get('X-CSRF-Token')).toBe('csrf-value')
  })

  it('coordinates one refresh for concurrent 401 responses and retries both requests', async () => {
    let protectedAttempts = 0
    let refreshAttempts = 0
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/auth/refresh')) {
        refreshAttempts += 1
        await Promise.resolve()
        return json({ refreshed: true })
      }
      protectedAttempts += 1
      return protectedAttempts <= 2
        ? new Response('{}', { status: 401, statusText: 'Unauthorized' })
        : json({ ok: true })
    })

    await expect(Promise.all([apiClient.get('/one'), apiClient.get('/two')])).resolves.toEqual([
      { ok: true },
      { ok: true },
    ])
    expect(refreshAttempts).toBe(1)
    expect(fetchMock).toHaveBeenCalledTimes(5)
  })

  it('notifies once when a coordinated refresh fails', async () => {
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401, statusText: 'Unauthorized' }))
    const results = await Promise.allSettled([apiClient.get('/one', { retry: 0 }), apiClient.get('/two', { retry: 0 })])
    expect(results.every((result) => result.status === 'rejected')).toBe(true)
    expect(unauthorized).toHaveBeenCalledTimes(1)
  })

  it('extracts download filename, MIME type and correlation ID', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('pdf', {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': "attachment; filename*=UTF-8''report%20one.pdf",
          'X-Correlation-Id': 'corr-1',
        },
      }),
    )
    const result = await apiClient.downloadWithMetadata('/exports/1')
    expect(result.fileName).toBe('report one.pdf')
    expect(result.mimeType).toBe('application/pdf')
    expect(result.correlationId).toBe('corr-1')
    expect(result.blob).toBeInstanceOf(Blob)
  })

  it('normalizes backend error statuses and keeps raw detail out of the friendly message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      json(
        {
          message: 'SQL table secret_x failed',
          errors: [{ field: 'name', code: 'required', message: 'Required' }],
          traceId: 'trace-1',
        },
        { status: 422, statusText: 'Unprocessable Entity' },
      ),
    )
    const error = await apiClient.post('/bad', {}).catch((e) => e as ApiError)
    expect(error.kind).toBe('validation')
    expect(error.correlationId).toBe('trace-1')
    expect(error.fieldErrors?.[0]).toMatchObject({ field: 'name', code: 'required' })
    expect(error.friendlyMessage).not.toContain('secret_x')
  })

  it.each([
    [400, 'validation'],
    [401, 'unauthorized'],
    [403, 'forbidden'],
    [404, 'not-found'],
    [409, 'conflict'],
    [429, 'rate-limit'],
    [500, 'server'],
    [503, 'maintenance'],
  ] as const)('maps HTTP %i to %s', async (status, kind) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status, statusText: 'Error' }))
    await expect(apiClient.get('/error', { retry: 0 })).rejects.toMatchObject({ kind })
  })

  it('retries GET but never retries POST by default', async () => {
    const getFetch = vi
      .spyOn(globalThis, 'fetch')
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(json({ ok: true }))
    await expect(apiClient.get('/retry', { retry: 1 })).resolves.toEqual({ ok: true })
    expect(getFetch).toHaveBeenCalledTimes(2)
    getFetch.mockClear().mockRejectedValue(new TypeError('offline'))
    await expect(apiClient.post('/no-retry', {})).rejects.toMatchObject({ kind: 'network' })
    expect(getFetch).toHaveBeenCalledTimes(1)
  })

  it('normalizes invalid JSON and cancellation', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response('{broken', { status: 200 }))
      .mockImplementationOnce(
        (_url, init) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
          }),
      )
    await expect(apiClient.get('/invalid', { retry: 0 })).rejects.toMatchObject({ kind: 'unknown' })
    const pending = apiClient.get('/cancel', { retry: 0 })
    cancelAllRequests()
    await expect(pending).rejects.toMatchObject({ kind: 'cancelled' })
  })

  it('distinguishes timeout from cancellation', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
        }),
    )
    await expect(apiClient.get('/slow', { timeoutMs: 5, retry: 0 })).rejects.toMatchObject({ kind: 'timeout' })
  })
})
