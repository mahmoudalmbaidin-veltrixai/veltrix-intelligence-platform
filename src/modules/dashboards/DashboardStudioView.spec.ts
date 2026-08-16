import { createPinia } from 'pinia'
import { enableAutoUnmount, flushPromises, shallowMount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/types/api'
import type { Dashboard, DashboardWidget } from '@/shared/types/dashboard'

const mocks = vi.hoisted(() => ({
  route: {
    name: 'dashboard-edit',
    path: '/dashboards/db-1/edit',
    fullPath: '/dashboards/db-1/edit',
    params: { id: 'db-1' },
  },
  replace: vi.fn(),
  leaveGuard: undefined as undefined | (() => boolean),
  get: vi.fn(),
  save: vi.fn(),
  publish: vi.fn(),
  listModels: vi.fn(),
  invalidate: vi.fn(),
  pushToast: vi.fn(),
}))

vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRoute: () => mocks.route,
  useRouter: () => ({ replace: mocks.replace }),
  isNavigationFailure: (failure: unknown) => Boolean(failure),
  onBeforeRouteLeave: (guard: () => boolean) => {
    mocks.leaveGuard = guard
  },
}))
vi.mock('./dashboards.service', () => ({
  dashboardService: {
    get: mocks.get,
    save: mocks.save,
    publish: mocks.publish,
  },
  newDashboard: () => makeDashboard('new'),
}))
vi.mock('@/modules/semantic/semantic.service', () => ({
  semanticStudioService: { listModels: mocks.listModels },
}))
vi.mock('@/shared/stores/platform', () => ({
  usePlatformStore: () => ({ can: () => true }),
}))
vi.mock('@/shared/stores/ui', () => ({
  useUiStore: () => ({ pushToast: mocks.pushToast }),
}))
vi.mock('@/shared/lib/query', () => ({ invalidateQueries: mocks.invalidate }))
vi.mock('@/shared/composables/useMediaQuery', () => ({
  useIsCompact: () => ({ value: false }),
}))
vi.mock('@/shared/composables/useResizable', () => ({
  useResizable: () => ({ width: { value: 280 }, start: vi.fn() }),
}))
vi.mock('@/shared/composables/useAnnouncer', () => ({ announce: vi.fn() }))

import DashboardStudioView from './DashboardStudioView.vue'

enableAutoUnmount(afterEach)

function makeDashboard(id = 'db-1', version = 3): Dashboard {
  return {
    id,
    name: 'Certification dashboard',
    description: '',
    status: 'draft',
    version,
    owner: 'owner',
    tags: [],
    pages: [{ id: 'page-1', name: 'Overview', widgets: [], filters: [] }],
    filters: [],
    updatedAt: '2026-08-05T00:00:00Z',
    favorite: false,
    freshness: '2026-08-05T00:00:00Z',
  }
}

function makeWidget(over: Partial<DashboardWidget> & { type: DashboardWidget['type'] }): DashboardWidget {
  return {
    id: over.id ?? `w-${over.type}`,
    type: over.type,
    modelId: over.modelId,
    pos: { x: 0, y: 0, w: 6, h: 5 },
    wells: over.wells ?? {},
    filters: [],
    format: {
      showTitle: true,
      showLegend: true,
      legendPosition: 'bottom',
      showDataLabels: false,
      showGridlines: true,
      decimals: 0,
      numberStyle: 'plain',
      border: true,
      padding: 12,
      conditional: [],
    },
    interactions: { crossFilter: true, drillDown: false, tooltip: true, exportable: true },
    general: { name: over.type, visible: true, locked: false },
  } as DashboardWidget
}
const validKpi = () =>
  makeWidget({
    id: 'kpi-ok',
    type: 'kpi',
    modelId: 'model',
    wells: { values: [{ fieldId: 'revenue', aggregation: 'sum' }] },
  })
const incompleteBar = () => makeWidget({ id: 'bar-bad', type: 'bar', modelId: 'model', wells: {} })
function dashboardWith(widgets: DashboardWidget[]): Dashboard {
  const d = makeDashboard()
  d.pages[0]!.widgets = widgets
  return d
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

type StudioVm = {
  save: (options?: { notify?: boolean }) => Promise<boolean>
  publish: () => Promise<void>
  editor: ReturnType<(typeof import('./useDashboardEditor'))['useDashboardEditor']>
  dirty: boolean
  conflict: boolean
}

async function mountStudio(options: { create?: boolean; dashboard?: Dashboard } = {}) {
  const source = options.dashboard ?? makeDashboard(options.create ? 'new' : 'db-1')
  Object.assign(
    mocks.route,
    options.create
      ? { name: 'dashboard-new', path: '/dashboards/new', fullPath: '/dashboards/new', params: {} }
      : {
          name: 'dashboard-edit',
          path: `/dashboards/${source.id}/edit`,
          fullPath: `/dashboards/${source.id}/edit`,
          params: { id: source.id },
        },
  )
  mocks.get.mockResolvedValue(source)
  mocks.listModels.mockResolvedValue([])
  const wrapper = shallowMount(DashboardStudioView, {
    global: { plugins: [createPinia()] },
  })
  await flushPromises()
  return wrapper as VueWrapper<StudioVm>
}

function dirtyEdit(wrapper: VueWrapper<StudioVm>, name = 'Edited locally') {
  wrapper.vm.editor.commit()
  wrapper.vm.editor.dashboard.name = name
}

describe('Dashboard Studio save coordinator behavior', () => {
  beforeEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    mocks.replace.mockResolvedValue(undefined)
    mocks.publish.mockImplementation(async (dashboard: Dashboard) => ({
      ...dashboard,
      status: 'published',
      version: dashboard.version + 1,
    }))
    mocks.leaveGuard = undefined
  })

  it('joins concurrent saves and preserves edits made while persistence is in flight', async () => {
    const wrapper = await mountStudio()
    dirtyEdit(wrapper, 'Snapshot title')
    const request = deferred<Dashboard>()
    mocks.save.mockReturnValue(request.promise)
    const first = wrapper.vm.save()
    const joined = wrapper.vm.save()
    wrapper.vm.editor.commit()
    wrapper.vm.editor.dashboard.name = 'Later local edit'
    request.resolve({ ...makeDashboard(), name: 'Snapshot title', version: 4 })
    expect(await first).toBe(true)
    expect(await joined).toBe(true)
    expect(mocks.save).toHaveBeenCalledOnce()
    expect(wrapper.vm.editor.dashboard.name).toBe('Later local edit')
    expect(wrapper.vm.editor.dashboard.version).toBe(4)
    expect(wrapper.vm.editor.dirty.value).toBe(true)
  })

  it('does not navigate after a failed create and preserves dirty state', async () => {
    const wrapper = await mountStudio({ create: true })
    dirtyEdit(wrapper)
    mocks.save.mockRejectedValue(ApiError.fromStatus(500))
    expect(await wrapper.vm.save()).toBe(false)
    expect(mocks.replace).not.toHaveBeenCalled()
    expect(wrapper.vm.editor.dirty.value).toBe(true)
  })

  it.each([422, 500])('preserves dirty update state after HTTP %s', async (status) => {
    const wrapper = await mountStudio()
    dirtyEdit(wrapper)
    mocks.save.mockRejectedValue(ApiError.fromStatus(status))
    expect(await wrapper.vm.save()).toBe(false)
    expect(wrapper.vm.editor.dirty.value).toBe(true)
    expect(wrapper.vm.conflict).toBe(false)
  })

  it('surfaces a 409 conflict without overwriting local edits', async () => {
    const wrapper = await mountStudio()
    dirtyEdit(wrapper)
    mocks.save.mockRejectedValue(ApiError.fromStatus(409, { code: 'DASHBOARD_VERSION_CONFLICT' }))
    expect(await wrapper.vm.save()).toBe(false)
    expect(wrapper.vm.conflict).toBe(true)
    expect(wrapper.vm.editor.dashboard.name).toBe('Edited locally')
    expect(wrapper.vm.editor.dirty.value).toBe(true)
  })

  it('stops publish when its prerequisite save fails', async () => {
    // A publishable (fully configured) dashboard so publish gets past the
    // readiness gate and actually depends on the save succeeding.
    const wrapper = await mountStudio({ dashboard: dashboardWith([validKpi()]) })
    dirtyEdit(wrapper)
    mocks.save.mockRejectedValue(ApiError.fromStatus(500))
    await wrapper.vm.publish()
    expect(mocks.publish).not.toHaveBeenCalled()
  })

  it('blocks save and publish for an incomplete Scatter without mutating the visual type', async () => {
    const dashboard = makeDashboard()
    const scatter: DashboardWidget = {
      id: 'legacy-scatter',
      type: 'scatter',
      pos: { x: 0, y: 0, w: 6, h: 5 },
      wells: { values: [{ fieldId: 'revenue', aggregation: 'sum' }] },
      filters: [],
      format: {
        showTitle: true,
        showLegend: true,
        legendPosition: 'bottom',
        showDataLabels: false,
        showGridlines: true,
        decimals: 0,
        numberStyle: 'plain',
        border: true,
        padding: 12,
        conditional: [],
      },
      interactions: { crossFilter: true, drillDown: false, tooltip: true, exportable: true },
      general: { name: 'Legacy Scatter', visible: true, locked: false },
    }
    dashboard.pages[0]!.widgets.push(scatter)
    const wrapper = await mountStudio({ dashboard })
    dirtyEdit(wrapper)

    expect(await wrapper.vm.save()).toBe(false)
    await wrapper.vm.publish()

    expect(mocks.save).not.toHaveBeenCalled()
    expect(mocks.publish).not.toHaveBeenCalled()
    expect(wrapper.vm.editor.dashboard.pages[0]!.widgets[0]!.type).toBe('scatter')
    expect(mocks.pushToast).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining('numeric Y measure') }),
    )
  })

  it('blocks a real unsaved route leave and bypasses only the confirmed create transition', async () => {
    const wrapper = await mountStudio({ create: true })
    dirtyEdit(wrapper)
    const navigation = deferred<undefined>()
    mocks.replace.mockReturnValue(navigation.promise)
    mocks.save.mockResolvedValue({ ...makeDashboard('created-1', 1), name: 'Edited locally' })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    expect(mocks.leaveGuard?.()).toBe(false)
    const save = wrapper.vm.save()
    await flushPromises()
    expect(mocks.leaveGuard?.()).toBe(true)
    navigation.resolve(undefined)
    expect(await save).toBe(true)
    wrapper.vm.editor.commit()
    wrapper.vm.editor.dashboard.name = 'Another edit'
    expect(mocks.leaveGuard?.()).toBe(false)
    expect(confirm).toHaveBeenCalled()
  })

  it('returns failure for router rejection after persistence and always restores the guard', async () => {
    const wrapper = await mountStudio({ create: true })
    dirtyEdit(wrapper)
    mocks.save.mockResolvedValue({ ...makeDashboard('created-2', 1), name: 'Edited locally' })
    mocks.replace.mockResolvedValue({ type: 4 })
    expect(await wrapper.vm.save()).toBe(false)
    wrapper.vm.editor.commit()
    expect(mocks.leaveGuard?.()).toBe(false)
  })

  it('invalidates dashboard cache only after successful persistence', async () => {
    const wrapper = await mountStudio()
    dirtyEdit(wrapper)
    mocks.save.mockResolvedValue({ ...makeDashboard(), name: 'Edited locally', version: 4 })
    expect(await wrapper.vm.save()).toBe(true)
    expect(mocks.invalidate).toHaveBeenCalledWith('dashboards:')
    mocks.invalidate.mockClear()
    dirtyEdit(wrapper, 'Fails')
    mocks.save.mockRejectedValue(ApiError.fromStatus(500))
    expect(await wrapper.vm.save()).toBe(false)
    expect(mocks.invalidate).not.toHaveBeenCalled()
  })

  it('deduplicates duplicate keyboard save submissions', async () => {
    const wrapper = await mountStudio()
    dirtyEdit(wrapper)
    const request = deferred<Dashboard>()
    mocks.save.mockReturnValue(request.promise)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true }))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true }))
    await flushPromises()
    expect(mocks.save).toHaveBeenCalledOnce()
    request.resolve({ ...makeDashboard(), name: 'Edited locally', version: 4 })
    await flushPromises()
  })

  it('joins autosave and manual save rather than issuing overlapping requests', async () => {
    vi.useFakeTimers()
    const wrapper = await mountStudio()
    const request = deferred<Dashboard>()
    mocks.save.mockReturnValue(request.promise)
    dirtyEdit(wrapper)
    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(2500)
    const manual = wrapper.vm.save()
    expect(mocks.save).toHaveBeenCalledOnce()
    request.resolve({ ...makeDashboard(), name: 'Edited locally', version: 4 })
    expect(await manual).toBe(true)
  })

  it('can reload the exact persisted aggregate immediately after save', async () => {
    const persisted = { ...makeDashboard(), name: 'Persisted', version: 4 }
    const wrapper = await mountStudio()
    dirtyEdit(wrapper, 'Persisted')
    mocks.save.mockResolvedValue(persisted)
    expect(await wrapper.vm.save()).toBe(true)
    wrapper.unmount()
    const refreshed = await mountStudio({ dashboard: persisted })
    expect(refreshed.vm.editor.dashboard.name).toBe('Persisted')
    expect(refreshed.vm.editor.dashboard.version).toBe(4)
    expect(refreshed.vm.editor.dirty.value).toBe(false)
  })

  // ---- CERT-P2-002: incomplete-widget / publish-readiness UX ----

  it('blocks save for an incomplete non-scatter widget and never calls the API', async () => {
    const wrapper = await mountStudio({ dashboard: dashboardWith([incompleteBar()]) })
    dirtyEdit(wrapper)
    expect(await wrapper.vm.save()).toBe(false)
    expect(mocks.save).not.toHaveBeenCalled()
    expect(mocks.pushToast).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'error',
        title: 'Complete this widget before saving',
        message: expect.stringContaining('Add at least one measure'),
      }),
    )
  })

  it('does not spam a validation toast during silent autosave', async () => {
    const wrapper = await mountStudio({ dashboard: dashboardWith([incompleteBar()]) })
    dirtyEdit(wrapper)
    expect(await wrapper.vm.save({ notify: false })).toBe(false)
    expect(mocks.save).not.toHaveBeenCalled()
    expect(mocks.pushToast).not.toHaveBeenCalled()
  })

  it('blocks publishing an empty dashboard with a helpful message', async () => {
    const wrapper = await mountStudio() // no widgets
    await wrapper.vm.publish()
    expect(mocks.publish).not.toHaveBeenCalled()
    expect(mocks.pushToast).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'error', message: expect.stringContaining('at least one configured widget') }),
    )
  })

  it('blocks publishing when a widget is incomplete', async () => {
    const wrapper = await mountStudio({ dashboard: dashboardWith([incompleteBar()]) })
    await wrapper.vm.publish()
    expect(mocks.publish).not.toHaveBeenCalled()
    expect(mocks.pushToast).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'error', message: expect.stringContaining('Finish configuring') }),
    )
  })

  it('publishes a fully configured dashboard', async () => {
    const wrapper = await mountStudio({ dashboard: dashboardWith([validKpi()]) })
    dirtyEdit(wrapper)
    mocks.save.mockResolvedValue({ ...dashboardWith([validKpi()]), name: 'Edited locally', version: 4 })
    await wrapper.vm.publish()
    expect(mocks.publish).toHaveBeenCalled()
    expect(mocks.pushToast).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'success', title: 'Dashboard published' }),
    )
  })

  it('translates an unexpected backend 422 into an incomplete-widget message', async () => {
    const wrapper = await mountStudio({ dashboard: dashboardWith([validKpi()]) })
    dirtyEdit(wrapper)
    mocks.save.mockRejectedValue(ApiError.fromStatus(422))
    expect(await wrapper.vm.save()).toBe(false)
    expect(mocks.pushToast).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'error',
        title: 'Dashboard was not saved',
        message: expect.stringContaining('widgets are incomplete'),
      }),
    )
  })
})
