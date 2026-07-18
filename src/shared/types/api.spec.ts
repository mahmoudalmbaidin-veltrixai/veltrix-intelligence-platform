import { describe, it, expect } from 'vitest'
import { ApiError, statusToKind } from './api'

describe('normalized error model', () => {
  it('maps HTTP status codes to categories', () => {
    expect(statusToKind(401)).toBe('unauthorized')
    expect(statusToKind(403)).toBe('forbidden')
    expect(statusToKind(404)).toBe('not-found')
    expect(statusToKind(409)).toBe('conflict')
    expect(statusToKind(422)).toBe('validation')
    expect(statusToKind(429)).toBe('rate-limit')
    expect(statusToKind(503)).toBe('maintenance')
    expect(statusToKind(500)).toBe('server')
  })

  it('builds a friendly, safe message per category', () => {
    expect(ApiError.fromStatus(403).friendlyMessage).toMatch(/permission/i)
    expect(ApiError.fromStatus(401).friendlyMessage).toMatch(/sign in/i)
  })

  it('marks transient errors retryable and client errors not', () => {
    expect(new ApiError('network', 'x').retryable).toBe(true)
    expect(new ApiError('timeout', 'x').retryable).toBe(true)
    expect(new ApiError('server', 'x').retryable).toBe(true)
    expect(new ApiError('validation', 'x').retryable).toBe(false)
    expect(new ApiError('forbidden', 'x').retryable).toBe(false)
    // A user cancellation is distinct from a timeout and must not be retried.
    expect(new ApiError('cancelled', 'x').retryable).toBe(false)
  })

  it('normalizes arbitrary throwables via from()', () => {
    expect(ApiError.from(new TypeError('fetch failed')).kind).toBe('network')
    const abort = new DOMException('aborted', 'AbortError')
    expect(ApiError.from(abort).kind).toBe('timeout')
    const existing = new ApiError('conflict', 'x')
    expect(ApiError.from(existing)).toBe(existing)
  })

  it('always carries a correlation id', () => {
    expect(new ApiError('server', 'x').correlationId.length).toBeGreaterThan(0)
  })
})
