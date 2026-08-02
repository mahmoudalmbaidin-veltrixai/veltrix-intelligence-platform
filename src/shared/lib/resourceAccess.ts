/**
 * Shared client contract + helpers for the caller's effective access to a
 * resource (dataset, connection, semantic model, …), as resolved by the backend
 * centralized authorization engine and echoed on the resource read response.
 *
 * The frontend consumes `allowedLevels` to render viewer/editor/operator/manager
 * (and denied) UI states and to show/hide the Share control (`canManageAccess`).
 * This is a UX convenience ONLY — the API independently authorizes every action;
 * frontend visibility is never the security boundary.
 */

/** Effective-access block returned by the backend (snake_case → camelCase mapped). */
export interface ResourceEffectiveAccess {
  level: string | null
  allowedLevels: string[]
  canManageAccess: boolean
  source: string
  reason: string
}

/** Raw backend shape (snake_case) as it arrives on the wire. */
export interface ResourceEffectiveAccessDto {
  level: string | null
  allowed_levels: string[]
  can_manage_access: boolean
  source: string
  reason: string
}

export function mapResourceAccess(
  dto: ResourceEffectiveAccessDto | null | undefined,
): ResourceEffectiveAccess | undefined {
  if (!dto) return undefined
  return {
    level: dto.level ?? null,
    allowedLevels: dto.allowed_levels ?? [],
    canManageAccess: dto.can_manage_access,
    source: dto.source,
    reason: dto.reason,
  }
}

/** Whether the caller is authorized for `level` on the resource (ladder-inclusive). */
export function resourceCan(access: ResourceEffectiveAccess | undefined, level: string): boolean {
  return !!access && access.allowedLevels.includes(level)
}

/** True when the backend resolved no access at all (explicit deny or no grant). */
export function resourceDenied(access: ResourceEffectiveAccess | undefined): boolean {
  return !!access && access.allowedLevels.length === 0
}
