/**
 * Centralized, typed HTTP client. Every live adapter goes through this — views,
 * components, composables and stores must NOT call `fetch` directly.
 *
 * Responsibilities: base URL, timeout + AbortController, standard headers
 * (auth, org/workspace context, locale, timezone, correlation id), retry with
 * backoff for idempotent requests, JSON / multipart / download, query params,
 * response + error parsing into the normalized ApiError model, and pagination
 * metadata extraction.
 */
import { config } from '@/shared/config/env'
import { ApiError, statusToKind, type FieldError } from '@/shared/types/api'

/** Injected so the client stays decoupled from Pinia (avoids circular imports). */
export interface RequestContext {
  token?: string
  orgId?: string
  workspaceId?: string
  locale?: string
  timezone?: string
}

let contextProvider: () => RequestContext = () => ({})
export function setRequestContextProvider(fn: () => RequestContext): void {
  contextProvider = fn
}

let onUnauthorized: (() => void) | undefined
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  query?: Record<string, string | number | boolean | undefined | null | Array<string | number>>
  body?: unknown
  /** multipart form data body (files). Takes precedence over `body`. */
  form?: FormData
  signal?: AbortSignal
  /** Number of retry attempts for retryable failures (default: GET=2, others=0). */
  retry?: number
  timeoutMs?: number
  headers?: Record<string, string>
  /** Expect a binary download instead of JSON. */
  download?: boolean
}

function buildQuery(query: RequestOptions['query']): string {
  if (!query) return ''
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v == null) continue
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, String(x)))
    else sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

function buildHeaders(opts: RequestOptions): Headers {
  const ctx = contextProvider()
  const headers = new Headers(opts.headers)
  headers.set('Accept', 'application/json')
  headers.set('X-Correlation-Id', crypto.randomUUID())
  if (!opts.form && opts.body !== undefined) headers.set('Content-Type', 'application/json')
  if (ctx.token) headers.set('Authorization', `Bearer ${ctx.token}`)
  if (ctx.orgId) headers.set('X-Organization-Id', ctx.orgId)
  if (ctx.workspaceId) headers.set('X-Workspace-Id', ctx.workspaceId)
  if (ctx.locale) headers.set('X-Locale', ctx.locale)
  if (ctx.timezone) headers.set('X-Timezone', ctx.timezone)
  return headers
}

async function parseError(res: Response): Promise<ApiError> {
  const correlationId = res.headers.get('X-Correlation-Id') ?? undefined
  const message = res.statusText
  let fieldErrors: FieldError[] | undefined
  let detail: string | undefined
  try {
    const data = await res.json()
    detail = typeof data?.message === 'string' ? data.message : undefined
    if (Array.isArray(data?.errors)) {
      fieldErrors = data.errors
        .filter((e: unknown): e is { field: string; message: string } => !!e && typeof e === 'object' && 'field' in e)
        .map((e: { field: string; message: string }) => ({ field: e.field, message: e.message }))
    }
  } catch {
    /* non-JSON error body */
  }
  return ApiError.fromStatus(res.status, { message, correlationId, fieldErrors, detail })
}

async function once<T>(path: string, opts: RequestOptions, controller: AbortController): Promise<{ data: T; res: Response }> {
  const url = `${config.apiBaseUrl}${path}${buildQuery(opts.query)}`
  const res = await fetch(url, {
    method: opts.method ?? 'GET',
    headers: buildHeaders(opts),
    body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
    signal: controller.signal,
    credentials: 'include',
  })

  if (res.status === 401) {
    onUnauthorized?.()
    throw await parseError(res)
  }
  if (!res.ok) throw await parseError(res)

  if (opts.download) {
    return { data: (await res.blob()) as unknown as T, res }
  }
  if (res.status === 204) return { data: undefined as unknown as T, res }
  const text = await res.text()
  return { data: (text ? JSON.parse(text) : undefined) as T, res }
}

/** Registry of in-flight controllers so a 401/session-expiry can cancel all. */
const inflight = new Set<AbortController>()
export function cancelAllRequests(): void {
  for (const c of inflight) c.abort()
  inflight.clear()
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const maxRetry = opts.retry ?? (opts.method && opts.method !== 'GET' ? 0 : 2)
  const timeout = opts.timeoutMs ?? config.apiTimeoutMs

  let attempt = 0
  for (;;) {
    const controller = new AbortController()
    inflight.add(controller)
    // Distinguish a timeout abort from a user/external cancellation.
    let timedOut = false
    const timer = setTimeout(() => { timedOut = true; controller.abort() }, timeout)
    const onAbort = () => controller.abort()
    opts.signal?.addEventListener('abort', onAbort)
    try {
      const { data } = await once<T>(path, opts, controller)
      return data
    } catch (raw) {
      // Classify aborts precisely: timeout vs user cancellation.
      if (raw instanceof DOMException && raw.name === 'AbortError') {
        throw new ApiError(timedOut ? 'timeout' : 'cancelled', timedOut ? 'The request timed out.' : 'The request was cancelled.')
      }
      const err = ApiError.from(raw)
      if (attempt < maxRetry && err.retryable && !opts.signal?.aborted) {
        attempt++
        await new Promise((r) => setTimeout(r, 250 * attempt))
        continue
      }
      throw err
    } finally {
      clearTimeout(timer)
      inflight.delete(controller)
      opts.signal?.removeEventListener('abort', onAbort)
    }
  }
}

export const apiClient = {
  get: <T>(path: string, opts?: Omit<RequestOptions, 'method' | 'body'>) => request<T>(path, { ...opts, method: 'GET' }),
  post: <T>(path: string, body?: unknown, opts?: Omit<RequestOptions, 'method'>) => request<T>(path, { ...opts, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, opts?: Omit<RequestOptions, 'method'>) => request<T>(path, { ...opts, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, opts?: Omit<RequestOptions, 'method'>) => request<T>(path, { ...opts, method: 'PATCH', body }),
  delete: <T>(path: string, opts?: Omit<RequestOptions, 'method' | 'body'>) => request<T>(path, { ...opts, method: 'DELETE' }),
  upload: <T>(path: string, form: FormData, opts?: Omit<RequestOptions, 'method' | 'body' | 'form'>) => request<T>(path, { ...opts, method: 'POST', form }),
  download: (path: string, opts?: Omit<RequestOptions, 'method' | 'download'>) => request<Blob>(path, { ...opts, method: 'GET', download: true }),
  /** Exposed for tests: builds the query string. */
  _buildQuery: buildQuery,
  _statusToKind: statusToKind,
}
