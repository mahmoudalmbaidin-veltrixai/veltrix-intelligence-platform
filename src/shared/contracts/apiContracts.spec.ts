import { describe, expect, it } from 'vitest'
import { z } from 'zod'
import {
  authenticationResponseSchema,
  normalizePage,
  pageDtoSchema,
  parseContract,
  sessionSchema,
} from './apiContracts'
import { ApiError } from '@/shared/types/api'

describe('runtime API contracts', () => {
  it('validates the B1 authentication response without tokens', () => {
    const value = authenticationResponseSchema.parse({
      user: { id: 'u1', email: 'admin@veltrix.local', display_name: 'VIP Admin', status: 'active' },
      session: { expires_at: '2026-07-21T12:00:00Z' },
    })
    expect(value.user.status).toBe('active')
  })
  it('normalizes totalItems pagination into the frontend Page model', () => {
    const dto = pageDtoSchema(z.object({ id: z.string() })).parse({
      items: [{ id: 'a' }],
      page: 1,
      pageSize: 10,
      totalItems: 21,
    })
    expect(normalizePage<{ id: string }>(dto)).toMatchObject({ total: 21, totalPages: 3, items: [{ id: 'a' }] })
  })

  it('rejects malformed critical identity DTOs at the adapter boundary', () => {
    expect(() => parseContract(sessionSchema, { expiresAt: '', context: { user: { id: 'x' } } }, 'session')).toThrow(
      ApiError,
    )
    try {
      parseContract(sessionSchema, {}, 'session')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).detail).toContain('context')
      expect((error as ApiError).friendlyMessage).not.toContain('context')
    }
  })
})
