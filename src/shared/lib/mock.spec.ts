import { describe, it, expect, beforeEach } from 'vitest'
import { LocalStore, setStorageScope, currentStorageScope } from './mock'

describe('LocalStore tenant scoping (VIP-FE-C002)', () => {
  beforeEach(() => {
    localStorage.clear()
    setStorageScope('global')
  })

  it('keeps unscoped stores shared across tenant scope changes', () => {
    const prefs = new LocalStore<{ theme: string }>('vip.prefs')
    prefs.write({ theme: 'dark' })
    setStorageScope('org_b:ws_b')
    expect(prefs.read({ theme: 'light' }).theme).toBe('dark')
  })

  it('partitions scoped stores so tenants cannot see each other’s data', () => {
    const store = new LocalStore<string[]>('vip.dashboards', { scoped: true })
    setStorageScope('org_veltrix:ws_analytics')
    store.write(['db_exec', 'db_revops'])

    // Switch tenant — the same store key now resolves to a different partition.
    setStorageScope('org_northwind:ws_sandbox')
    expect(store.read([])).toEqual([])

    store.write(['db_only_northwind'])
    // Switch back — original tenant data is intact and isolated.
    setStorageScope('org_veltrix:ws_analytics')
    expect(store.read([])).toEqual(['db_exec', 'db_revops'])
  })

  it('exposes the current scope', () => {
    setStorageScope('org_x:ws_y')
    expect(currentStorageScope()).toBe('org_x:ws_y')
    setStorageScope('')
    expect(currentStorageScope()).toBe('global')
  })
})
