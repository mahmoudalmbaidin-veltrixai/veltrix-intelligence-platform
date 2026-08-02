import { describe, it, expect, beforeEach } from 'vitest'
import { useDashboardEditor } from './useDashboardEditor'
import { newDashboard } from './dashboards.service'

describe('useDashboardEditor', () => {
  let editor: ReturnType<typeof useDashboardEditor>
  beforeEach(() => {
    editor = useDashboardEditor({ ...newDashboard(), id: 'db_test' })
  })

  it('adds a widget to the active page', () => {
    editor.addWidget('bar')
    expect(editor.widgets.value).toHaveLength(1)
    expect(editor.widgets.value[0].type).toBe('bar')
  })

  it('selects the newly added widget', () => {
    const w = editor.addWidget('kpi')
    expect(editor.selectedId.value).toBe(w.id)
    expect(editor.selectedWidget.value?.id).toBe(w.id)
  })

  it('moves and resizes a widget via updatePosition', () => {
    const w = editor.addWidget('line')
    editor.updatePosition(w.id, { x: 3, y: 2, w: 8, h: 6 })
    expect(editor.widgets.value[0].pos).toEqual({ x: 3, y: 2, w: 8, h: 6 })
  })

  it('updates widget configuration via patchWidget', () => {
    const w = editor.addWidget('bar')
    editor.patchWidget(w.id, { general: { ...w.general, name: 'Sales by region' } })
    expect(editor.selectedWidget.value?.general.name).toBe('Sales by region')
  })

  it('duplicates and deletes widgets', () => {
    const w = editor.addWidget('pie')
    editor.duplicateWidget(w.id)
    expect(editor.widgets.value).toHaveLength(2)
    editor.deleteWidget(w.id)
    expect(editor.widgets.value).toHaveLength(1)
  })

  it('supports undo/redo of widget operations', () => {
    editor.addWidget('bar')
    editor.addWidget('line')
    expect(editor.widgets.value).toHaveLength(2)
    editor.undo()
    expect(editor.widgets.value).toHaveLength(1)
    editor.redo()
    expect(editor.widgets.value).toHaveLength(2)
  })

  it('copies and pastes a widget', () => {
    const w = editor.addWidget('kpi')
    editor.copyWidget(w.id)
    editor.paste()
    expect(editor.widgets.value).toHaveLength(2)
  })

  it('manages multiple pages', () => {
    expect(editor.dashboard.pages).toHaveLength(1)
    editor.addPage()
    expect(editor.dashboard.pages).toHaveLength(2)
    expect(editor.activePageId.value).toBe(editor.dashboard.pages[1].id)
    editor.removePage(editor.dashboard.pages[1].id)
    expect(editor.dashboard.pages).toHaveLength(1)
  })

  it('keeps at least one page', () => {
    editor.removePage(editor.dashboard.pages[0].id)
    expect(editor.dashboard.pages).toHaveLength(1)
  })

  it('tracks dirty state', () => {
    editor.addWidget('bar')
    expect(editor.dirty.value).toBe(true)
    editor.markSaved()
    expect(editor.dirty.value).toBe(false)
  })

  // --- widget identity + reconciliation guards ---

  it('gives a duplicated widget a new unique id with equivalent config', () => {
    const original = editor.addWidget('bar')
    editor.patchWidget(original.id, { general: { ...original.general, name: 'Revenue' } })
    editor.duplicateWidget(original.id)
    const [a, b] = editor.widgets.value
    expect(a.id).not.toBe(b.id) // unique identity
    expect(b.type).toBe(a.type) // equivalent config (type carried over)
    expect(b.general.name).toBe('Revenue copy') // distinguishable copy label
    expect(b).not.toBe(a) // not the same object reference
    expect(b.general).not.toBe(a.general) // deep-cloned, no shared references
  })

  it('editing one widget never mutates another', () => {
    const first = editor.addWidget('bar')
    const second = editor.addWidget('line')
    editor.patchWidget(first.id, { general: { ...first.general, name: 'Only first' } })
    const secondAfter = editor.widgets.value.find((w) => w.id === second.id)!
    expect(secondAfter.general.name).not.toBe('Only first')
    expect(editor.widgets.value.find((w) => w.id === first.id)!.general.name).toBe('Only first')
  })

  it('reconciles editor state from a save response (server ids replace temp ids)', () => {
    // Simulate the studio hydrating from the persisted server payload after save.
    const local = useDashboardEditor({ ...newDashboard(), id: 'db_test' })
    const tmp = local.addWidget('kpi')
    expect(tmp.id.startsWith('w_')).toBe(true) // temporary client id before save
    // Server returns the same widget with a stable UUID under the same page.
    const serverId = '11111111-1111-4111-8111-111111111111'
    const persisted = {
      ...local.dashboard,
      pages: local.dashboard.pages.map((p, i) =>
        i === 0 ? { ...p, widgets: p.widgets.map((w) => ({ ...w, id: serverId })) } : p,
      ),
    }
    const rebuilt = useDashboardEditor(persisted)
    expect(rebuilt.widgets.value).toHaveLength(1)
    expect(rebuilt.widgets.value[0].id).toBe(serverId) // reconciled to the server id
    expect(rebuilt.dirty.value).toBe(false) // freshly hydrated state is clean
  })
})
