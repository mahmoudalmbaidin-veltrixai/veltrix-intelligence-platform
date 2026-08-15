/**
 * BUG-CUR-004 — centralized V1 production feature availability.
 *
 * Some modules ship in the codebase but are not production-ready for V1
 * (placeholder/stub surfaces with no backend). They must be hidden from
 * production navigation AND blocked on direct-URL/deep-link access, regardless
 * of a user's role or entitlement grants — a super admin must not be able to
 * reach them either. In development mock mode they remain reachable so work can
 * continue.
 *
 * This is the single source of truth consulted by both navigation visibility
 * (`canExposeNavigationItem`) and route access (the router `beforeEach` guard).
 * Feature availability and authorization are independent: a surface is shown
 * only when it is BOTH available in this build AND the user is authorized.
 *
 * To promote a module into V1 later, remove its entitlement key / path here and
 * the existing entitlement + permission checks take over — the gate is fully
 * reversible without touching every page.
 */
import { config, type ApiMode } from '@/shared/config/env'
import type { EntitlementKey } from '@/shared/types/identity'

/** Entitlements whose modules are outside the V1 production scope. */
export const V1_GATED_ENTITLEMENTS: ReadonlySet<EntitlementKey> = new Set<EntitlementKey>([
  'insights',
  'report_studio',
  'ai_studio',
  'automation',
  'marketplace',
  'developer_api',
  'billing',
])

/** V1-gated surfaces that carry no entitlement, matched by exact path or prefix. */
export const V1_GATED_PATHS: readonly string[] = ['/explore']

/**
 * True when a navigation item or route points at a module that is gated out of
 * this (production) build. Mock mode is never gated so development can proceed.
 */
export function isProductionGatedFeature(
  target: { entitlement?: EntitlementKey; path?: string },
  apiMode: ApiMode = config.apiMode,
): boolean {
  if (apiMode === 'mock') return false
  if (target.entitlement && V1_GATED_ENTITLEMENTS.has(target.entitlement)) return true
  const path = target.path
  if (path && V1_GATED_PATHS.some((prefix) => path === prefix || path.startsWith(`${prefix}/`))) {
    return true
  }
  return false
}
