import { describe, expect, it } from 'vitest'
import { canExposeNavigationItem, type NavItem, type NavigationAccess } from './navigation'

const aiItem: NavItem = {
  label: 'Knowledge Bases',
  to: '/ai/knowledge',
  icon: 'book',
  permission: 'ai.configure',
  entitlement: 'ai_studio',
  featureFlag: 'ai_studio',
  developmentMockOnly: true,
}

function access(flag: boolean, entitlement: boolean): NavigationAccess {
  return {
    isPlatformAdmin: false,
    can: () => true,
    entitled: () => entitlement,
    flagEnabled: () => flag,
  }
}

describe('AI preview production disposition', () => {
  it.each([
    [false, false],
    [true, false],
    [false, true],
    [true, true],
  ])('never exposes incomplete AI navigation in live mode (flag=%s entitlement=%s)', (flag, entitlement) => {
    expect(canExposeNavigationItem(aiItem, access(flag, entitlement), 'live')).toBe(false)
  })

  it('requires both flag and entitlement in permitted development mock mode', () => {
    expect(canExposeNavigationItem(aiItem, access(false, false), 'mock')).toBe(false)
    expect(canExposeNavigationItem(aiItem, access(true, false), 'mock')).toBe(false)
    expect(canExposeNavigationItem(aiItem, access(false, true), 'mock')).toBe(false)
    expect(canExposeNavigationItem(aiItem, access(true, true), 'mock')).toBe(true)
  })
})
