import { describe, expect, it } from 'vitest'
import { NAV_GROUPS, canExposeNavigationItem, type NavItem, type NavigationAccess } from './navigation'
import { V1_GATED_ENTITLEMENTS, isProductionGatedFeature } from './featureAvailability'

/** A maximally-privileged principal: platform super admin with every permission,
 * entitlement, and feature flag. Used to prove the V1 gate is independent of
 * authorization — elevated access must NOT reveal gated modules in production. */
const SUPER_ADMIN: NavigationAccess = {
  isPlatformAdmin: true,
  can: () => true,
  entitled: () => true,
  flagEnabled: () => true,
}

function navItem(to: string): NavItem | undefined {
  return NAV_GROUPS.flatMap((g) => g.items).find((i) => i.to === to)
}

const GATED_PATHS = [
  '/reports',
  '/insights',
  '/explore',
  '/automation',
  '/automation/runs',
  '/automation/approvals',
  '/marketplace',
  '/developer',
  '/billing',
  '/ai/studio',
]
const CORE_V1_PATHS = [
  '/connections',
  '/datasets',
  '/pipelines',
  '/dashboards',
  '/dashboards/deliveries',
  '/notifications',
]

describe('isProductionGatedFeature', () => {
  it('gates every out-of-scope entitlement in production (live)', () => {
    for (const entitlement of V1_GATED_ENTITLEMENTS) {
      expect(isProductionGatedFeature({ entitlement }, 'live')).toBe(true)
    }
  })

  it('does not gate core V1 entitlements', () => {
    for (const entitlement of ['connection_studio', 'pipeline_studio', 'dashboard_studio']) {
      expect(isProductionGatedFeature({ entitlement }, 'live')).toBe(false)
    }
  })

  it('gates entitlement-less paths (Explore, Developer settings) by path in production', () => {
    expect(isProductionGatedFeature({ path: '/explore' }, 'live')).toBe(true)
    expect(isProductionGatedFeature({ path: '/settings/developer' }, 'live')).toBe(true)
    expect(isProductionGatedFeature({ path: '/dashboards' }, 'live')).toBe(false)
  })

  it('is reversible: nothing is gated in development mock mode', () => {
    expect(isProductionGatedFeature({ entitlement: 'report_studio' }, 'mock')).toBe(false)
    expect(isProductionGatedFeature({ path: '/explore' }, 'mock')).toBe(false)
    expect(isProductionGatedFeature({ path: '/settings/developer' }, 'mock')).toBe(false)
  })
})

describe('canExposeNavigationItem — V1 production gate', () => {
  it('hides every gated module in production even for a super admin', () => {
    for (const path of GATED_PATHS) {
      const item = navItem(path)
      expect(item, `nav item ${path} should exist`).toBeTruthy()
      expect(canExposeNavigationItem(item!, SUPER_ADMIN, 'live')).toBe(false)
    }
  })

  it('keeps core V1 modules visible in production', () => {
    for (const path of CORE_V1_PATHS) {
      const item = navItem(path)
      expect(item, `nav item ${path} should exist`).toBeTruthy()
      expect(canExposeNavigationItem(item!, SUPER_ADMIN, 'live')).toBe(true)
    }
  })

  it('re-exposes gated modules in mock mode (gate is reversible for future releases)', () => {
    const reports = navItem('/reports')!
    expect(canExposeNavigationItem(reports, SUPER_ADMIN, 'live')).toBe(false)
    expect(canExposeNavigationItem(reports, SUPER_ADMIN, 'mock')).toBe(true)
  })
})
