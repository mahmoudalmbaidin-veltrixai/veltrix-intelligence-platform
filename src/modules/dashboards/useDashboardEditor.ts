/**
 * Dashboard editor engine — pages + widgets grid model with full history,
 * selection, add/move/resize/duplicate/delete/copy-paste and dirty tracking.
 */
import { computed, reactive, ref } from 'vue'
import type { Dashboard, DashboardWidget, GridPosition, WidgetType } from '@/shared/types/dashboard'
import { createWidget } from './widgetFactory'
import { clone } from '@/shared/lib/mock'

export const GRID_COLS = 12

export function useDashboardEditor(initial: Dashboard) {
  const dashboard = reactive<Dashboard>(clone(initial))
  const activePageId = ref(dashboard.pages[0]?.id ?? '')
  const selectedId = ref<string | null>(null)

  const undoStack = ref<string[]>([])
  const redoStack = ref<string[]>([])
  const clipboard = ref<DashboardWidget | null>(null)
  const dirty = ref(false)
  let savedSnap = snap()

  function snap(): string {
    return JSON.stringify({ pages: dashboard.pages, name: dashboard.name, filters: dashboard.filters })
  }
  function commit() {
    undoStack.value.push(snap())
    if (undoStack.value.length > 80) undoStack.value.shift()
    redoStack.value = []
    // A commit always precedes a mutation, so the layout is about to diverge.
    dirty.value = true
  }
  function apply(s: string) {
    const p = JSON.parse(s) as Pick<Dashboard, 'pages' | 'name' | 'filters'>
    dashboard.pages = p.pages
    dashboard.name = p.name
    dashboard.filters = p.filters
    dirty.value = snap() !== savedSnap
  }
  const canUndo = computed(() => undoStack.value.length > 0)
  const canRedo = computed(() => redoStack.value.length > 0)
  function undo() { if (undoStack.value.length) { redoStack.value.push(snap()); apply(undoStack.value.pop()!); selectedId.value = null } }
  function redo() { if (redoStack.value.length) { undoStack.value.push(snap()); apply(redoStack.value.pop()!); selectedId.value = null } }
  function markSaved() { savedSnap = snap(); dirty.value = false }

  const activePage = computed(() => dashboard.pages.find((p) => p.id === activePageId.value) ?? dashboard.pages[0])
  const widgets = computed(() => activePage.value?.widgets ?? [])
  const selectedWidget = computed(() => widgets.value.find((w) => w.id === selectedId.value) ?? null)

  /* ---- placement helper: find first free-ish row ---- */
  function nextPosition(w: number, h: number): GridPosition {
    const maxY = widgets.value.reduce((m, wi) => Math.max(m, wi.pos.y + wi.pos.h), 0)
    return { x: 0, y: maxY, w, h }
  }

  function addWidget(type: WidgetType): DashboardWidget {
    commit()
    const tmp = createWidget(type, 0, 0)
    tmp.pos = { ...tmp.pos, ...nextPosition(tmp.pos.w, tmp.pos.h) }
    activePage.value.widgets.push(tmp)
    selectedId.value = tmp.id
    return tmp
  }

  function updatePosition(id: string, pos: GridPosition) {
    const wi = widgets.value.find((w) => w.id === id)
    if (wi) { wi.pos = pos; dirty.value = true }
  }
  function beginChange() { commit() }

  function deleteWidget(id: string) {
    commit()
    activePage.value.widgets = activePage.value.widgets.filter((w) => w.id !== id)
    if (selectedId.value === id) selectedId.value = null
  }
  function duplicateWidget(id: string) {
    const wi = widgets.value.find((w) => w.id === id)
    if (!wi) return
    commit()
    const copy = clone(wi)
    copy.id = `w_${Date.now().toString(36)}${Math.floor(Math.random() * 999)}`
    copy.pos = { ...copy.pos, ...nextPosition(copy.pos.w, copy.pos.h) }
    copy.general = { ...copy.general, name: `${copy.general.name} copy` }
    activePage.value.widgets.push(copy)
    selectedId.value = copy.id
  }
  function copyWidget(id: string) {
    const wi = widgets.value.find((w) => w.id === id)
    if (wi) clipboard.value = clone(wi)
  }
  function paste() {
    if (!clipboard.value) return
    commit()
    const copy = clone(clipboard.value)
    copy.id = `w_${Date.now().toString(36)}${Math.floor(Math.random() * 999)}`
    copy.pos = { ...copy.pos, ...nextPosition(copy.pos.w, copy.pos.h) }
    activePage.value.widgets.push(copy)
    selectedId.value = copy.id
  }

  function patchWidget(id: string, patch: Partial<DashboardWidget>) {
    const idx = activePage.value.widgets.findIndex((w) => w.id === id)
    if (idx < 0) return
    commit()
    activePage.value.widgets[idx] = { ...activePage.value.widgets[idx], ...patch }
  }
  function select(id: string | null) { selectedId.value = id }

  /* ---- pages ---- */
  function addPage() {
    commit()
    const id = `pg_${Date.now().toString(36)}`
    dashboard.pages.push({ id, name: `Page ${dashboard.pages.length + 1}`, widgets: [], filters: [] })
    activePageId.value = id
  }
  function removePage(id: string) {
    if (dashboard.pages.length <= 1) return
    commit()
    dashboard.pages = dashboard.pages.filter((p) => p.id !== id)
    if (activePageId.value === id) activePageId.value = dashboard.pages[0].id
  }
  function renamePage(id: string, name: string) {
    const p = dashboard.pages.find((x) => x.id === id)
    if (p) { commit(); p.name = name }
  }

  return {
    dashboard, activePageId, activePage, widgets, selectedId, selectedWidget,
    dirty, canUndo, canRedo, clipboard,
    addWidget, updatePosition, beginChange, deleteWidget, duplicateWidget, copyWidget, paste, patchWidget, select,
    addPage, removePage, renamePage,
    undo, redo, commit, markSaved,
  }
}

export type DashboardEditor = ReturnType<typeof useDashboardEditor>
