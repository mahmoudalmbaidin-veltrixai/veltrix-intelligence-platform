/**
 * Shared API envelope + normalized error contracts used by every typed service.
 * Mock adapters and (future) live adapters both conform to these.
 */

export interface Page<T> {
  items: T[]
  /** Canonical total; `totalItems` is accepted at DTO mapping boundaries. */
  total: number
  page: number
  pageSize: number
  totalPages: number
  cursor?: string
  nextCursor?: string
  previousCursor?: string
}

export interface ListParams {
  page?: number
  pageSize?: number
  search?: string
  sort?: string
  sortDir?: 'asc' | 'desc'
  filters?: Record<string, string | string[] | number | boolean | undefined>
}

/** Normalized frontend error categories — independent of transport. */
export type ApiErrorKind =
  | 'validation'
  | 'unauthorized'
  | 'forbidden'
  | 'not-found'
  | 'conflict'
  | 'rate-limit'
  | 'server'
  | 'network'
  | 'timeout'
  | 'cancelled'
  | 'maintenance'
  | 'unknown'

export interface FieldError {
  field: string
  code?: string
  message: string
}

export type AsyncJobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'partially_completed'

export interface AsyncJob<TResult = unknown> {
  id: string
  status: AsyncJobStatus
  progress: number
  currentStep?: string
  startedAt?: string
  completedAt?: string
  result?: TResult
  error?: { message: string; code?: string; correlationId?: string }
  canRetry: boolean
  canCancel: boolean
}

export interface UploadContract<TResult = unknown> {
  acceptedTypes: string[]
  maxSizeBytes: number
  progress: number
  status: 'pending' | 'uploading' | 'scanning' | 'succeeded' | 'failed' | 'cancelled'
  result?: TResult
  errors?: FieldError[]
  multipart?: { uploadId: string; partSizeBytes: number }
}

export interface DownloadContract {
  blob: Blob
  fileName: string
  mimeType: string
  correlationId?: string
}

/** Human-friendly, safe messages per category (never leak raw backend text). */
const FRIENDLY: Record<ApiErrorKind, string> = {
  validation: 'Please correct the highlighted fields and try again.',
  unauthorized: 'Your session has expired. Please sign in again.',
  forbidden: 'You don’t have permission to perform this action.',
  'not-found': 'The requested resource could not be found.',
  conflict: 'This action conflicts with the current state. Refresh and try again.',
  'rate-limit': 'Too many requests. Please wait a moment and retry.',
  server: 'Something went wrong on our side. Please try again.',
  network: 'Network error — check your connection and retry.',
  timeout: 'The request took too long. Please try again.',
  cancelled: 'The request was cancelled.',
  maintenance: 'The service is temporarily unavailable for maintenance.',
  unknown: 'An unexpected error occurred.',
}

export class ApiError extends Error {
  kind: ApiErrorKind
  correlationId: string
  fieldErrors?: FieldError[]
  /** Technical detail — shown only in dev / diagnostics, never as the primary UI message. */
  detail?: string
  status?: number
  code?: string

  constructor(
    kind: ApiErrorKind,
    message: string,
    opts?: { correlationId?: string; fieldErrors?: FieldError[]; detail?: string; status?: number; code?: string },
  ) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.correlationId = opts?.correlationId ?? crypto.randomUUID().slice(0, 8)
    this.fieldErrors = opts?.fieldErrors
    this.detail = opts?.detail
    this.status = opts?.status
    this.code = opts?.code
  }

  /** Safe, user-facing message. */
  get friendlyMessage(): string {
    return FRIENDLY[this.kind]
  }

  /** Whether a retry is sensible for this category. */
  get retryable(): boolean {
    return this.kind === 'network' || this.kind === 'timeout' || this.kind === 'server' || this.kind === 'rate-limit'
  }

  /** Map an HTTP status code to a normalized error. */
  static fromStatus(
    status: number,
    opts?: { message?: string; correlationId?: string; fieldErrors?: FieldError[]; detail?: string; code?: string },
  ): ApiError {
    const kind = statusToKind(status)
    return new ApiError(kind, opts?.message ?? FRIENDLY[kind], { ...opts, status })
  }

  static from(error: unknown): ApiError {
    if (error instanceof ApiError) return error
    if (error instanceof DOMException && error.name === 'AbortError') {
      return new ApiError('timeout', 'The request was cancelled or timed out.')
    }
    if (error instanceof TypeError) {
      return new ApiError('network', 'A network error occurred.', { detail: error.message })
    }
    return new ApiError('unknown', 'An unexpected error occurred.', { detail: String(error) })
  }
}

export function statusToKind(status: number): ApiErrorKind {
  if (status === 400 || status === 422) return 'validation'
  if (status === 401) return 'unauthorized'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'not-found'
  if (status === 409) return 'conflict'
  if (status === 429) return 'rate-limit'
  if (status === 503) return 'maintenance'
  if (status >= 500) return 'server'
  if (status >= 400) return 'unknown'
  return 'unknown'
}

export type ApiMode = 'mock' | 'live'
