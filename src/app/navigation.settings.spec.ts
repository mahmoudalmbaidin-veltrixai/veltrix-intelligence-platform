import { describe, expect, it } from 'vitest'
import { NAV_GROUPS } from './navigation'

describe('Settings navigation is de-duplicated', () => {
  const settings = NAV_GROUPS.find((g) => g.key === 'settings')

  it('exposes a single personal Settings entry', () => {
    expect(settings).toBeTruthy()
    expect(settings?.items).toHaveLength(1)
    expect(settings?.items[0]?.to).toBe('/settings/profile')
  })

  it('no longer advertises Workspace or Organization settings inside Settings', () => {
    const labels = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.label))
    expect(labels).not.toContain('Workspace Settings')
    expect(labels).not.toContain('Organization Settings')
    expect(labels).not.toContain('Personal Settings')
  })
})
