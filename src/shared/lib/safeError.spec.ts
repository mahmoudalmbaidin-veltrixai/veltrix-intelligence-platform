import { describe, it, expect } from 'vitest'
import { toSafeError, safeErrorText } from './safeError'
import { ApiError } from '@/shared/types/api'

describe('safeError', () => {
  it('surfaces the backend message + code for an ApiError (no internals)', () => {
    const e = new ApiError('conflict', 'This dashboard has active delivery schedules.', {
      code: 'DASHBOARD_VERSION_CONFLICT',
      correlationId: 'abc123',
    })
    const s = toSafeError(e)
    expect(s.message).toBe('This dashboard has active delivery schedules.')
    expect(s.code).toBe('DASHBOARD_VERSION_CONFLICT')
    expect(s.correlationId).toBe('abc123')
    expect(safeErrorText(e)).toBe('This dashboard has active delivery schedules. (DASHBOARD_VERSION_CONFLICT)')
  })

  it('falls back to the friendly per-kind message when no detail is present', () => {
    const e = new ApiError('forbidden', 'forbidden')
    // message === kind → use friendlyMessage instead of echoing the kind
    expect(toSafeError(e).message).not.toBe('forbidden')
    expect(toSafeError(e).message.length).toBeGreaterThan(0)
  })

  it('handles plain Errors and unknown values safely', () => {
    expect(toSafeError(new Error('boom')).message).toBe('boom')
    expect(toSafeError('weird').message).toBe('Something went wrong. Please try again.')
    expect(toSafeError(undefined).message).toBe('Something went wrong. Please try again.')
  })
})
