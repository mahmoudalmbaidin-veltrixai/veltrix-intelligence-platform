import { describe, it, expect } from 'vitest'
import { mapResourceAccess, resourceCan, resourceDenied, type ResourceEffectiveAccessDto } from './resourceAccess'

const dto = (level: string | null, allowed: string[], canManage = false): ResourceEffectiveAccessDto => ({
  level,
  allowed_levels: allowed,
  can_manage_access: canManage,
  source: 'resource_grant',
  reason: 'GRANTED',
})

describe('resourceAccess helpers', () => {
  it('maps the backend snake_case DTO to camelCase', () => {
    const access = mapResourceAccess(dto('edit', ['query', 'export', 'edit'], true))
    expect(access).toEqual({
      level: 'edit',
      allowedLevels: ['query', 'export', 'edit'],
      canManageAccess: true,
      source: 'resource_grant',
      reason: 'GRANTED',
    })
  })

  it('returns undefined for a missing access block', () => {
    expect(mapResourceAccess(undefined)).toBeUndefined()
    expect(mapResourceAccess(null)).toBeUndefined()
  })

  it('resourceCan reflects the allowed level ladder', () => {
    const access = mapResourceAccess(dto('operator', ['use', 'test']))
    expect(resourceCan(access, 'use')).toBe(true)
    expect(resourceCan(access, 'test')).toBe(true)
    expect(resourceCan(access, 'edit')).toBe(false)
    expect(resourceCan(access, 'rotate')).toBe(false)
  })

  it('resourceCan is false when access is undefined (no leak)', () => {
    expect(resourceCan(undefined, 'edit')).toBe(false)
  })

  it('resourceDenied is true only when access resolved with no levels', () => {
    expect(resourceDenied(mapResourceAccess(dto(null, [])))).toBe(true)
    expect(resourceDenied(mapResourceAccess(dto('query', ['query'])))).toBe(false)
    expect(resourceDenied(undefined)).toBe(false)
  })

  it('canManageAccess is carried through for the Share control', () => {
    expect(mapResourceAccess(dto('manage', ['view', 'query', 'edit', 'manage'], true))?.canManageAccess).toBe(true)
    expect(mapResourceAccess(dto('view', ['view']))?.canManageAccess).toBe(false)
  })
})
