import { describe, expect, it } from 'vitest'
import { resourceCan, mapResourceAccess } from '@/shared/lib/resourceAccess'

describe('Dataset live tab permission helpers', () => {
  it('maps certify separately from edit', () => {
    const editOnly = mapResourceAccess({
      level: 'edit',
      allowed_levels: ['query', 'export', 'edit'],
      can_manage_access: false,
      source: 'resource_grant',
      reason: 'GRANTED',
    })
    expect(resourceCan(editOnly, 'edit')).toBe(true)
    expect(resourceCan(editOnly, 'certify')).toBe(false)

    const certifier = mapResourceAccess({
      level: 'certify',
      allowed_levels: ['query', 'export', 'edit', 'certify'],
      can_manage_access: false,
      source: 'resource_grant',
      reason: 'GRANTED',
    })
    expect(resourceCan(certifier, 'certify')).toBe(true)
    expect(certifier?.canManageAccess).toBe(false)
  })

  it('query is required for preview; export is distinct', () => {
    const queryOnly = mapResourceAccess({
      level: 'query',
      allowed_levels: ['query'],
      can_manage_access: false,
      source: 'role',
      reason: 'GRANTED',
    })
    expect(resourceCan(queryOnly, 'query')).toBe(true)
    expect(resourceCan(queryOnly, 'export')).toBe(false)
  })
})
