/**
 * Shared API envelope + error contracts used by every typed service.
 * The mock adapters and (future) live adapters both conform to these.
 */

export interface Page<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export interface ListParams {
  page?: number
  pageSize?: number
  search?: string
  sort?: string
  sortDir?: 'asc' | 'desc'
  filters?: Record<string, string | string[] | number | boolean | undefined>
}

export type ApiErrorKind =
  | 'validation'
  | 'unauthorized'
  | 'forbidden'
  | 'not-found'
  | 'conflict'
  | 'server'
  | 'network'
  | 'timeout'

export interface FieldError {
  field: string
  message: string
}

export class ApiError extends Error {
  kind: ApiErrorKind
  correlationId: string
  fieldErrors?: FieldError[]
  detail?: string

  constructor(kind: ApiErrorKind, message: string, opts?: { correlationId?: string; fieldErrors?: FieldError[]; detail?: string }) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.correlationId = opts?.correlationId ?? crypto.randomUUID().slice(0, 8)
    this.fieldErrors = opts?.fieldErrors
    this.detail = opts?.detail
  }
}

export type ApiMode = 'mock' | 'live'
