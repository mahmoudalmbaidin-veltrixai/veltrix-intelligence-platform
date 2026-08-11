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
import { invalidateAllQueries } from '@/shared/lib/query'
import { ApiError, statusToKind, type DownloadContract, type FieldError } from '@/shared/types/api'
import { errorEnvelopeSchema, standardErrorEnvelopeSchema } from '@/shared/contracts/apiContracts'

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
let onTenantAccessLost: (() => void) | undefined
let unauthorizedNotified = false
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn
  unauthorizedNotified = false
}

export function setTenantAccessLostHandler(fn: () => void): void {
  onTenantAccessLost = fn
}

function notifyUnauthorizedOnce(): void {
  if (unauthorizedNotified) return
  unauthorizedNotified = true
  onUnauthorized?.()
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  query?: Record<
    string,
    string | number | boolean | undefined | null | Array<string | number> | Record<string, unknown>
  >
  body?: unknown
  /** multipart form data body (files). Takes precedence over `body`. */
  form?: FormData
  /** Raw request body for streaming/file endpoints. */
  rawBody?: BodyInit
  signal?: AbortSignal
  /** Number of retry attempts for retryable failures (default: GET=2, others=0). */
  retry?: number
  timeoutMs?: number
  headers?: Record<string, string>
  /** Expect a binary download instead of JSON. */
  download?: boolean
  /** Prevent recursive refresh for authentication endpoints. */
  skipAuthRefresh?: boolean
  /** Authentication failures normally clear frontend state. */
  notifyOnUnauthorized?: boolean
}

function readCookie(name: string): string | undefined {
  if (typeof document === 'undefined') return undefined
  const prefix = `${encodeURIComponent(name)}=`
  const value = document.cookie
    .split('; ')
    .find((entry) => entry.startsWith(prefix))
    ?.slice(prefix.length)
  return value ? decodeURIComponent(value) : undefined
}

function buildQuery(query: RequestOptions['query']): string {
  if (!query) return ''
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v == null) continue
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, String(x)))
    else if (typeof v === 'object') {
      for (const [nestedKey, nestedValue] of Object.entries(v)) {
        if (nestedValue != null) sp.set(`${k}[${nestedKey}]`, String(nestedValue))
      }
    } else sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

/** The single API version prefix every versioned application route resolves under. */
export const API_VERSION_PREFIX = '/api/v1'

/**
 * Paths that are served at the API root, NOT under `/api/v1`. Authentication is
 * deliberately unversioned (session cookies are platform infrastructure), and
 * health/readiness are infra probes. These pass through with the configured
 * origin and never receive the version prefix.
 */
function isUnversionedRootPath(path: string): boolean {
  return path === '/auth' || path.startsWith('/auth/') || path === '/health' || path === '/ready' || path === '/healthz'
}

/**
 * Canonical URL resolver — the ONE rule for turning an adapter path into a full
 * request URL. Adapters must NOT re-implement prefix logic.
 *
 * Behaviour (robust to how `VITE_API_BASE_URL` is configured):
 *  - Absolute URLs (`http(s)://…`, e.g. signed downloads / external hosts) pass
 *    through untouched.
 *  - The configured base is normalized to an API *origin* by stripping trailing
 *    slashes and a trailing `/api/v1`, so `http://host` and `http://host/api/v1`
 *    resolve identically.
 *  - Unversioned root paths (`/auth/*`, `/health`, `/ready`) keep the origin only.
 *  - Already-versioned paths (`/api/v1/…`) are used as-is (never duplicated).
 *  - Every other application path receives `/api/v1` exactly once.
 *  - Query strings are appended after the resolved path.
 *
 * Pure and side-effect free so it can be unit-tested with any base URL.
 */
export function resolveApiUrl(baseUrl: string, path: string, query?: RequestOptions['query']): string {
  const suffix = buildQuery(query)
  // Absolute URL (signed download, external host, SSE origin) — never rewrite.
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(path)) return `${path}${suffix}`

  const origin = baseUrl.replace(/\/+$/, '').replace(/\/api\/v1$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  if (isUnversionedRootPath(normalizedPath)) return `${origin}${normalizedPath}${suffix}`
  if (normalizedPath === API_VERSION_PREFIX || normalizedPath.startsWith(`${API_VERSION_PREFIX}/`)) {
    return `${origin}${normalizedPath}${suffix}`
  }
  return `${origin}${API_VERSION_PREFIX}${normalizedPath}${suffix}`
}

function buildUrl(path: string, query: RequestOptions['query']): string {
  return resolveApiUrl(config.apiBaseUrl, path, query)
}

function buildHeaders(opts: RequestOptions): Headers {
  const ctx = contextProvider()
  const headers = new Headers(opts.headers)
  headers.set('Accept', 'application/json')
  headers.set('X-Correlation-Id', crypto.randomUUID())
  if (!opts.form && !opts.rawBody && opts.body !== undefined) headers.set('Content-Type', 'application/json')
  if (opts.method && !['GET'].includes(opts.method)) {
    const csrf = readCookie(config.authCsrfCookieName)
    if (csrf) headers.set(config.authCsrfHeaderName, csrf)
  }
  if (ctx.token) headers.set('Authorization', `Bearer ${ctx.token}`)
  if (ctx.orgId) headers.set('X-Organization-Id', ctx.orgId)
  if (ctx.workspaceId) headers.set('X-Workspace-Id', ctx.workspaceId)
  if (ctx.locale) headers.set('X-Locale', ctx.locale)
  if (ctx.timezone) headers.set('X-Timezone', ctx.timezone)
  return headers
}

async function parseError(res: Response): Promise<ApiError> {
  const correlationId = res.headers.get('X-Correlation-Id') ?? res.headers.get('X-Trace-Id') ?? undefined
  const message = res.statusText
  let fieldErrors: FieldError[] | undefined
  let detail: string | undefined
  try {
    const body: unknown = await res.json()
    const standard = standardErrorEnvelopeSchema.safeParse(body)
    if (standard.success) {
      detail = standard.data.error.message
      fieldErrors = standard.data.error.details
        ?.filter((item): item is { field: string; message: string } => !!item.field)
        .map((item) => ({ field: item.field, message: item.message }))
      return ApiError.fromStatus(res.status, {
        message,
        correlationId: correlationId ?? standard.data.error.correlation_id,
        fieldErrors,
        detail,
        code: standard.data.error.code,
      })
    }
    const parsed = errorEnvelopeSchema.safeParse(body)
    if (parsed.success) {
      detail = parsed.data.message
      fieldErrors = parsed.data.errors
      if (!correlationId && parsed.data.traceId)
        return ApiError.fromStatus(res.status, { message, correlationId: parsed.data.traceId, fieldErrors, detail })
    }
  } catch {
    /* non-JSON error body */
  }
  return ApiError.fromStatus(res.status, { message, correlationId, fieldErrors, detail })
}

async function once<T>(
  path: string,
  opts: RequestOptions,
  controller: AbortController,
): Promise<{ data: T; res: Response }> {
  const url = buildUrl(path, opts.query)
  const res = await fetch(url, {
    method: opts.method ?? 'GET',
    headers: buildHeaders(opts),
    body: opts.form ?? opts.rawBody ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
    signal: controller.signal,
    credentials: 'include',
  })

  if (!res.ok) throw await parseError(res)

  if (opts.download) {
    return { data: (await res.blob()) as unknown as T, res }
  }
  if (res.status === 204) return { data: undefined as unknown as T, res }
  const text = await res.text()
  return { data: (text ? JSON.parse(text) : undefined) as T, res }
}

function fileNameFromDisposition(value: string | null): string {
  if (!value) return 'download'
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(value)?.[1]
  const plain = /filename="?([^";]+)"?/i.exec(value)?.[1]
  const selected = utf8 ?? plain
  try {
    return selected ? decodeURIComponent(selected) : 'download'
  } catch {
    return selected ?? 'download'
  }
}

async function downloadWithMetadata(
  path: string,
  opts: Omit<RequestOptions, 'method' | 'download'> = {},
): Promise<DownloadContract> {
  const controller = new AbortController()
  const { data, res } = await once<Blob>(path, { ...opts, method: 'GET', download: true }, controller)
  return {
    blob: data,
    fileName: fileNameFromDisposition(res.headers.get('Content-Disposition')),
    mimeType: res.headers.get('Content-Type') ?? data.type ?? 'application/octet-stream',
    correlationId: res.headers.get('X-Correlation-Id') ?? res.headers.get('X-Trace-Id') ?? undefined,
  }
}

export interface ServerEvent<T = unknown> {
  id: string
  type: string
  data: T
}

async function* eventStream<T>(
  path: string,
  opts: Omit<RequestOptions, 'method' | 'body' | 'form' | 'download' | 'rawBody'> = {},
): AsyncGenerator<ServerEvent<T>> {
  const response = await fetch(buildUrl(path, opts.query), {
    method: 'GET',
    headers: buildHeaders({ ...opts, method: 'GET' }),
    credentials: 'include',
    signal: opts.signal,
  })
  if (!response.ok) throw await parseError(response)
  if (!response.body) throw new ApiError('network', 'The event stream is unavailable.')
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) return
      buffer += value.replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const fields = new Map<string, string>()
        const dataLines: string[] = []
        for (const line of block.split('\n')) {
          if (!line.startsWith(':')) {
            const separator = line.indexOf(':')
            if (separator > 0) {
              const key = line.slice(0, separator)
              const fieldValue = line.slice(separator + 1).trimStart()
              if (key === 'data') dataLines.push(fieldValue)
              else fields.set(key, fieldValue)
            }
          }
        }
        const data = dataLines.join('\n')
        if (data) {
          yield {
            id: fields.get('id') ?? '',
            type: fields.get('event') ?? 'message',
            data: JSON.parse(data) as T,
          }
        }
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
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
  let authRefreshAttempted = false
  for (;;) {
    const controller = new AbortController()
    inflight.add(controller)
    // Distinguish a timeout abort from a user/external cancellation.
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, timeout)
    const onAbort = () => controller.abort()
    opts.signal?.addEventListener('abort', onAbort)
    try {
      const { data } = await once<T>(path, opts, controller)
      unauthorizedNotified = false
      // A successful mutation can change server state any view depends on, so
      // drop the query cache and let mounted views refetch immediately. The
      // silent token refresh is excluded to avoid refetch storms.
      const method = opts.method ?? 'GET'
      if (method !== 'GET' && !opts.download && path !== '/auth/refresh') {
        invalidateAllQueries()
      }
      return data
    } catch (raw) {
      // Classify aborts precisely: timeout vs user cancellation.
      if (raw instanceof DOMException && raw.name === 'AbortError') {
        throw new ApiError(
          timedOut ? 'timeout' : 'cancelled',
          timedOut ? 'The request timed out.' : 'The request was cancelled.',
        )
      }
      const err = ApiError.from(raw)
      if (
        ['forbidden', 'not-found'].includes(err.kind) &&
        err.code &&
        [
          'ORGANIZATION_NOT_FOUND',
          'ORGANIZATION_ACCESS_DENIED',
          'WORKSPACE_NOT_FOUND',
          'WORKSPACE_ACCESS_DENIED',
          'MEMBERSHIP_INACTIVE',
        ].includes(err.code)
      ) {
        onTenantAccessLost?.()
      }
      if (err.kind === 'unauthorized' && !opts.skipAuthRefresh && !authRefreshAttempted) {
        authRefreshAttempted = true
        try {
          await coordinatedRefresh()
          continue
        } catch {
          notifyUnauthorizedOnce()
          throw err
        }
      }
      if (err.kind === 'unauthorized' && opts.notifyOnUnauthorized !== false) notifyUnauthorizedOnce()
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

let refreshPromise: Promise<void> | null = null
async function coordinatedRefresh(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = request<unknown>('/auth/refresh', {
      method: 'POST',
      retry: 0,
      skipAuthRefresh: true,
      notifyOnUnauthorized: false,
    })
      .then(() => undefined)
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

export const apiClient = {
  get: <T>(path: string, opts?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...opts, method: 'GET' }),
  post: <T>(path: string, body?: unknown, opts?: Omit<RequestOptions, 'method'>) =>
    request<T>(path, { ...opts, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, opts?: Omit<RequestOptions, 'method'>) =>
    request<T>(path, { ...opts, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, opts?: Omit<RequestOptions, 'method'>) =>
    request<T>(path, { ...opts, method: 'PATCH', body }),
  delete: <T>(path: string, opts?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...opts, method: 'DELETE' }),
  upload: <T>(path: string, form: FormData, opts?: Omit<RequestOptions, 'method' | 'body' | 'form'>) =>
    request<T>(path, { ...opts, method: 'POST', form }),
  uploadRaw: <T>(path: string, body: BodyInit, opts?: Omit<RequestOptions, 'method' | 'body' | 'form' | 'rawBody'>) =>
    request<T>(path, { ...opts, method: 'POST', rawBody: body }),
  download: (path: string, opts?: Omit<RequestOptions, 'method' | 'download'>) =>
    request<Blob>(path, { ...opts, method: 'GET', download: true }),
  downloadWithMetadata,
  eventStream,
  /** Exposed for tests: builds the query string. */
  _buildQuery: buildQuery,
  _buildUrl: buildUrl,
  _statusToKind: statusToKind,
}
