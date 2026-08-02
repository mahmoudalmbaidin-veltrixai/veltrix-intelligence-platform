/**
 * Derives Pipeline Studio capability states from the backend's effective-access
 * decision (echoed on the pipeline read response). This is the single place the
 * UI reads to decide which controls to enable — viewer/operator/developer/owner
 * and the denied state — so it always mirrors what the API will enforce.
 *
 * Frontend visibility is a convenience, NOT the security boundary: every action
 * is independently authorized by the backend. When no backend access block is
 * present (a brand-new local draft, or offline mock mode) we fall back to the
 * caller's broad workspace permissions so authoring still works.
 */
import { computed, type ComputedRef, type Ref } from 'vue'
import type { Pipeline, PipelineAccessLevel } from '@/shared/types/pipeline'
import { usePlatformStore } from '@/shared/stores/platform'

export interface PipelinePermissions {
  /** Highest effective level, or null when access is denied. */
  level: ComputedRef<PipelineAccessLevel | null>
  /** Open/read the pipeline (viewer). */
  canView: ComputedRef<boolean>
  /** Execute: run / cancel / retry (operator). */
  canRun: ComputedRef<boolean>
  /** Author: edit graph, save drafts, validate, publish (developer). */
  canEdit: ComputedRef<boolean>
  /** Administer: archive / delete / manage sharing (owner). */
  canManage: ComputedRef<boolean>
  /** True when the backend resolved no access at all (explicit deny or no grant). */
  denied: ComputedRef<boolean>
  /** Whether the backend supplied an effective-access block for this pipeline. */
  hasBackendAccess: ComputedRef<boolean>
}

export function usePipelinePermissions(pipeline: Ref<Pipeline | undefined>): PipelinePermissions {
  const platform = usePlatformStore()

  const access = computed(() => pipeline.value?.access)
  // A brand-new, unsaved draft has no server identity yet; the create gate
  // governs it, so treat it as authorable via the broad permission fallback.
  const isNewDraft = computed(() => !pipeline.value || pipeline.value.id === 'new')
  const hasBackendAccess = computed(() => !isNewDraft.value && access.value != null)

  // Fallbacks used only when the backend did not supply an access block.
  const fallbackEdit = computed(() => platform.can('pipeline.update') || platform.can('pipeline.create'))
  const fallbackRun = computed(() => platform.can('pipeline.execute') || fallbackEdit.value)
  const fallbackManage = computed(() => platform.can('pipeline.delete') || platform.can('pipeline.update'))

  const canView = computed(() => (hasBackendAccess.value ? !!access.value?.canView : true))
  const canRun = computed(() => (hasBackendAccess.value ? !!access.value?.canRun : fallbackRun.value))
  const canEdit = computed(() => (hasBackendAccess.value ? !!access.value?.canEdit : fallbackEdit.value))
  const canManage = computed(() => (hasBackendAccess.value ? !!access.value?.canManage : fallbackManage.value))
  const denied = computed(() => hasBackendAccess.value && !access.value?.canView)
  const level = computed<PipelineAccessLevel | null>(() =>
    hasBackendAccess.value ? (access.value?.level ?? null) : isNewDraft.value ? 'owner' : null,
  )

  return { level, canView, canRun, canEdit, canManage, denied, hasBackendAccess }
}
