import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { usePipelinePermissions } from './usePipelinePermissions'
import { newDraft } from './pipelines.service'
import type { Pipeline, PipelineAccess, PipelineAccessLevel } from '@/shared/types/pipeline'

// Controllable broad-permission fallback (mock/legacy mode only).
const granted = new Set<string>()
vi.mock('@/shared/stores/platform', () => ({
  usePlatformStore: () => ({ can: (perm?: string) => (perm ? granted.has(perm) : false) }),
}))

function access(level: PipelineAccessLevel | null, allowed: PipelineAccessLevel[]): PipelineAccess {
  return {
    level,
    allowedLevels: allowed,
    canView: allowed.includes('viewer'),
    canRun: allowed.includes('operator'),
    canEdit: allowed.includes('developer'),
    canManage: allowed.includes('owner'),
    source: 'resource_grant',
    reason: 'GRANTED',
  }
}

function pipeline(acc?: PipelineAccess, id = 'pl_1'): Pipeline {
  return { ...newDraft(), id, access: acc }
}

describe('usePipelinePermissions', () => {
  beforeEach(() => granted.clear())

  it('viewer access: can view only, no run/edit/manage', () => {
    const p = usePipelinePermissions(ref(pipeline(access('viewer', ['viewer']))))
    expect(p.canView.value).toBe(true)
    expect(p.canRun.value).toBe(false)
    expect(p.canEdit.value).toBe(false)
    expect(p.canManage.value).toBe(false)
    expect(p.level.value).toBe('viewer')
    expect(p.denied.value).toBe(false)
  })

  it('operator access: adds run, still no edit/manage', () => {
    const p = usePipelinePermissions(ref(pipeline(access('operator', ['viewer', 'operator']))))
    expect(p.canRun.value).toBe(true)
    expect(p.canEdit.value).toBe(false)
    expect(p.canManage.value).toBe(false)
    expect(p.level.value).toBe('operator')
  })

  it('developer access: adds edit, still no manage', () => {
    const p = usePipelinePermissions(ref(pipeline(access('developer', ['viewer', 'operator', 'developer']))))
    expect(p.canRun.value).toBe(true)
    expect(p.canEdit.value).toBe(true)
    expect(p.canManage.value).toBe(false)
    expect(p.level.value).toBe('developer')
  })

  it('owner access: full capability set', () => {
    const p = usePipelinePermissions(ref(pipeline(access('owner', ['viewer', 'operator', 'developer', 'owner']))))
    expect(p.canView.value).toBe(true)
    expect(p.canRun.value).toBe(true)
    expect(p.canEdit.value).toBe(true)
    expect(p.canManage.value).toBe(true)
    expect(p.level.value).toBe('owner')
  })

  it('denied access: no capabilities and denied flag set', () => {
    const p = usePipelinePermissions(ref(pipeline(access(null, []))))
    expect(p.canView.value).toBe(false)
    expect(p.canRun.value).toBe(false)
    expect(p.canEdit.value).toBe(false)
    expect(p.canManage.value).toBe(false)
    expect(p.denied.value).toBe(true)
    expect(p.level.value).toBe(null)
  })

  it('backend access takes precedence over broad permissions', () => {
    // Even a user holding broad edit permission is bound to a viewer resource grant.
    granted.add('pipeline.update')
    const p = usePipelinePermissions(ref(pipeline(access('viewer', ['viewer']))))
    expect(p.canEdit.value).toBe(false)
    expect(p.hasBackendAccess.value).toBe(true)
  })

  it('new draft is authorable via the create permission fallback', () => {
    granted.add('pipeline.create')
    const p = usePipelinePermissions(ref({ ...newDraft() })) // id === 'new'
    expect(p.hasBackendAccess.value).toBe(false)
    expect(p.canEdit.value).toBe(true)
    expect(p.level.value).toBe('owner')
  })

  it('new draft without create permission is not editable', () => {
    const p = usePipelinePermissions(ref({ ...newDraft() }))
    expect(p.canEdit.value).toBe(false)
  })

  it('legacy pipeline without access block falls back to broad edit permission', () => {
    granted.add('pipeline.update')
    const p = usePipelinePermissions(ref(pipeline(undefined)))
    expect(p.hasBackendAccess.value).toBe(false)
    expect(p.canEdit.value).toBe(true)
    expect(p.canRun.value).toBe(true) // edit implies run in fallback
  })

  it('legacy pipeline fallback: execute permission grants run without edit', () => {
    granted.add('pipeline.execute')
    const p = usePipelinePermissions(ref(pipeline(undefined)))
    expect(p.canRun.value).toBe(true)
    expect(p.canEdit.value).toBe(false)
  })

  it('legacy pipeline fallback: delete permission grants manage', () => {
    granted.add('pipeline.delete')
    const p = usePipelinePermissions(ref(pipeline(undefined)))
    expect(p.canManage.value).toBe(true)
  })

  it('reacts when the pipeline access changes', () => {
    const source = ref(pipeline(access('viewer', ['viewer'])))
    const p = usePipelinePermissions(source)
    expect(p.canEdit.value).toBe(false)
    source.value = pipeline(access('developer', ['viewer', 'operator', 'developer']))
    expect(p.canEdit.value).toBe(true)
    expect(p.level.value).toBe('developer')
  })

  it('undefined pipeline is treated as a new draft (no crash)', () => {
    const p = usePipelinePermissions(ref(undefined))
    expect(p.canView.value).toBe(true)
    expect(p.hasBackendAccess.value).toBe(false)
  })

  it('non-owner backend level surfaces for the toolbar badge', () => {
    const viewer = usePipelinePermissions(ref(pipeline(access('viewer', ['viewer']))))
    const owner = usePipelinePermissions(ref(pipeline(access('owner', ['viewer', 'operator', 'developer', 'owner']))))
    expect(viewer.level.value).toBe('viewer')
    expect(owner.level.value).toBe('owner')
  })
})
