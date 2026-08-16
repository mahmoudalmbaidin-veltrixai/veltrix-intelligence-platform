import { describe, expect, it } from 'vitest'
import type { QueryFilter, SemanticField } from '@/shared/types/semantic'
import {
  buildDashboardFilter,
  defaultOperatorForField,
  draftFromFilter,
  migrateDraft,
  operatorsForField,
  valueInputType,
} from './filterAuthoring'

const category: SemanticField = {
  id: 'category',
  name: 'category',
  label: 'Category',
  role: 'dimension',
  dataType: 'string',
}
const orderDate: SemanticField = {
  id: 'order_date',
  name: 'order_date',
  label: 'Order Date',
  role: 'time',
  dataType: 'date',
}
const amount: SemanticField = { id: 'amount', name: 'amount', label: 'Amount', role: 'dimension', dataType: 'number' }

describe('operatorsForField', () => {
  it('offers Equals + Is one of for categorical fields', () => {
    expect(operatorsForField(category).map((o) => o.value)).toEqual(['eq', 'in'])
  })
  it('offers Equals + Between for date and numeric fields', () => {
    expect(operatorsForField(orderDate).map((o) => o.value)).toEqual(['eq', 'between'])
    expect(operatorsForField(amount).map((o) => o.value)).toEqual(['eq', 'between'])
  })
  it('defaults to eq and maps value input types', () => {
    expect(defaultOperatorForField(category)).toBe('eq')
    expect(valueInputType(orderDate)).toBe('date')
    expect(valueInputType(amount)).toBe('number')
    expect(valueInputType(category)).toBe('text')
  })
})

describe('buildDashboardFilter', () => {
  it('builds an eq filter', () => {
    const { filter } = buildDashboardFilter(category, 'eq', { value: 'Electronics' })
    expect(filter).toMatchObject({ fieldId: 'category', operator: 'eq', value: 'Electronics' })
  })

  it('builds an in filter with an array value', () => {
    const { filter } = buildDashboardFilter(category, 'in', { values: ['Electronics', 'Furniture'] })
    expect(filter).toMatchObject({ fieldId: 'category', operator: 'in', value: ['Electronics', 'Furniture'] })
    expect(filter?.label).toContain('is one of')
  })

  it('builds a between filter with two bounds', () => {
    const { filter } = buildDashboardFilter(orderDate, 'between', { from: '2026-01-01', to: '2026-12-31' })
    expect(filter).toMatchObject({ operator: 'between', value: ['2026-01-01', '2026-12-31'] })
  })

  it('rejects an empty in list', () => {
    const result = buildDashboardFilter(category, 'in', { values: ['  ', ''] })
    expect(result.filter).toBeUndefined()
    expect(result.error).toMatch(/at least one value/i)
  })

  it('rejects a between missing a bound', () => {
    expect(buildDashboardFilter(orderDate, 'between', { from: '2026-01-01' }).error).toMatch(/both/i)
  })

  it('rejects an inverted date range and numeric range', () => {
    expect(buildDashboardFilter(orderDate, 'between', { from: '2026-12-31', to: '2026-01-01' }).error).toMatch(/after/i)
    expect(buildDashboardFilter(amount, 'between', { from: '100', to: '10' }).error).toMatch(/after/i)
  })

  it('accepts an ascending numeric range (numeric, not lexical, comparison)', () => {
    // '9' > '100' lexically but 9 < 100 numerically — must be accepted.
    expect(buildDashboardFilter(amount, 'between', { from: '9', to: '100' }).filter).toBeDefined()
  })

  it('rejects an empty eq value', () => {
    expect(buildDashboardFilter(category, 'eq', { value: '   ' }).error).toMatch(/enter a value/i)
  })
})

describe('operator + field switching', () => {
  it('seeds the in list from the previous scalar when switching eq → in', () => {
    expect(migrateDraft('in', { value: 'Electronics' })).toEqual({ values: ['Electronics'] })
  })
  it('seeds the from bound when switching to between', () => {
    expect(migrateDraft('between', { value: '2026-01-01' })).toEqual({ from: '2026-01-01', to: '' })
  })
  it('collapses back to a single scalar when switching to eq', () => {
    expect(migrateDraft('eq', { values: ['A', 'B'] })).toEqual({ value: 'A' })
  })
})

describe('draftFromFilter (chip edit round-trip)', () => {
  it('rehydrates an in filter', () => {
    const f: QueryFilter = { fieldId: 'category', operator: 'in', value: ['A', 'B'] }
    expect(draftFromFilter(f)).toEqual({ operator: 'in', draft: { values: ['A', 'B'] } })
  })
  it('rehydrates a between filter', () => {
    const f: QueryFilter = { fieldId: 'order_date', operator: 'between', value: ['2026-01-01', '2026-12-31'] }
    expect(draftFromFilter(f)).toEqual({ operator: 'between', draft: { from: '2026-01-01', to: '2026-12-31' } })
  })
  it('rehydrates an eq filter', () => {
    const f: QueryFilter = { fieldId: 'category', operator: 'eq', value: 'Electronics' }
    expect(draftFromFilter(f)).toEqual({ operator: 'eq', draft: { value: 'Electronics' } })
  })
})
