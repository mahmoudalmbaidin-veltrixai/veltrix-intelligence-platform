import { describe, it, expect } from 'vitest'
import { hasPermission, permissionsFor, ROLES } from './roles'

describe('permissions', () => {
  it('grants everything to platform admins', () => {
    const perms = permissionsFor('platform-admin')
    expect(hasPermission(perms, 'billing:manage')).toBe(true)
    expect(hasPermission(perms, 'admin:platform')).toBe(true)
  })

  it('restricts business viewers to read-only', () => {
    const perms = permissionsFor('business-viewer')
    expect(hasPermission(perms, 'dashboard:read')).toBe(true)
    expect(hasPermission(perms, 'dashboard:write')).toBe(false)
    expect(hasPermission(perms, 'pipeline:write')).toBe(false)
  })

  it('lets data engineers write pipelines but not manage billing', () => {
    const perms = permissionsFor('data-engineer')
    expect(hasPermission(perms, 'pipeline:write')).toBe(true)
    expect(hasPermission(perms, 'pipeline:publish')).toBe(true)
    expect(hasPermission(perms, 'billing:manage')).toBe(false)
  })

  it('lets analysts author dashboards but not pipelines', () => {
    const perms = permissionsFor('analyst')
    expect(hasPermission(perms, 'dashboard:write')).toBe(true)
    expect(hasPermission(perms, 'pipeline:write')).toBe(false)
  })

  it('treats an undefined required permission as allowed', () => {
    expect(hasPermission(permissionsFor('business-viewer'), undefined)).toBe(true)
  })

  it('defines every role with a label', () => {
    for (const key of Object.keys(ROLES)) {
      expect(ROLES[key as keyof typeof ROLES].label.length).toBeGreaterThan(0)
    }
  })
})
