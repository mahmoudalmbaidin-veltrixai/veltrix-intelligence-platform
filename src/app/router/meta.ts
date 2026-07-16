import 'vue-router'
import type { EntitlementKey, FeatureFlagKey, Permission } from '@/shared/types/identity'

export type LayoutType = 'app' | 'studio' | 'settings' | 'auth' | 'blank' | 'error'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    layout?: LayoutType
    requiresAuth?: boolean
    permission?: Permission
    entitlement?: EntitlementKey
    featureFlag?: FeatureFlagKey
    navGroup?: string
    breadcrumb?: string
    keywords?: string[]
    /** Full-bleed studio hides page padding + uses studio chrome. */
    fullBleed?: boolean
  }
}
