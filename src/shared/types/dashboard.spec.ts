import { describe, it, expect } from 'vitest'
import { toQuery } from './dashboard'
import { createWidget } from '@/modules/dashboards/widgetFactory'

describe('toQuery (widget → semantic query)', () => {
  it('maps axis + values wells into dimensions and measures', () => {
    const w = createWidget('column', 0, 0)
    const q = toQuery(w)
    expect(q.dimensions.some((d) => d.fieldId === 'region')).toBe(true)
    expect(q.measures.some((m) => m.fieldId === 'revenue')).toBe(true)
  })

  it('merges cross-filters into the query filters', () => {
    const w = createWidget('bar', 0, 0)
    const q = toQuery(w, [{ fieldId: 'region', operator: 'eq', value: 'EMEA' }])
    expect(q.filters.some((f) => f.fieldId === 'region' && f.value === 'EMEA')).toBe(true)
  })

  it('deduplicates dimensions across wells', () => {
    const w = createWidget('stacked-bar', 0, 0)
    w.wells.legend = ['region'] // same as xAxis default
    const q = toQuery(w)
    const regionCount = q.dimensions.filter((d) => d.fieldId === 'region').length
    expect(regionCount).toBe(1)
  })
})
