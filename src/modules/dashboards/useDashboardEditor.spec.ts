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
})
