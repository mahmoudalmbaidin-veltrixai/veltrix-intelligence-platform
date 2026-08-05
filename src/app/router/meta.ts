import 'vue-router'
import type { EntitlementKey, FeatureFlagKey, Permission } from '@/shared/types/identity'

export type LayoutType = 'app' | 'studio' | 'settings' | 'auth' | 'blank' | 'error'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    layout?: LayoutType
    requiresAuth?: boolean
    requiresOrganization?: boolean
    requiresWorkspace?: boolean
    /** Platform super-admin (cross-tenant operator) only. Non-admins get a 404. */
    requiresPlatformAdmin?: boolean
    /** Guest-only route (e.g. login); redirects authenticated users to home. */
    publicOnly?: boolean
    permission?: Permission
    entitlement?: EntitlementKey
    featureFlag?: FeatureFlagKey
    /** Preview-only route that must never resolve in live API mode. */
    developmentMockOnly?: boolean
    navGroup?: string
    breadcrumb?: string
    keywords?: string[]
    /** Full-bleed studio hides page padding + uses studio chrome. */
    fullBleed?: boolean
  }
}
