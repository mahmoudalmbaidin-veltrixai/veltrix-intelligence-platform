import { describe, it, expect } from 'vitest'
import { runQuerySync, MODELS } from './semanticModels'
import type { SemanticQuery } from '@/shared/types/semantic'

describe('semantic query engine (mock)', () => {
  it('exposes certified sales and ops models', () => {
    expect(MODELS.map((m) => m.id)).toContain('sm_sales')
    expect(MODELS.map((m) => m.id)).toContain('sm_ops')
  })

  it('returns one row per category for a single dimension', () => {
    const q: SemanticQuery = {
      modelId: 'sm_sales',
      dimensions: [{ fieldId: 'region' }],
      measures: [{ fieldId: 'revenue', aggregation: 'sum' }],
      filters: [],
    }
    const result = runQuerySync(q)
    expect(result.rows.length).toBe(4) // EMEA, Americas, APAC, MEA
    expect(result.columns.map((c) => c.key)).toEqual(['region', 'revenue'])
    expect(result.simulated).toBe(true)
  })

  it('produces deterministic values for the same query', () => {
    const q: SemanticQuery = {
      modelId: 'sm_sales',
      dimensions: [{ fieldId: 'category' }],
      measures: [{ fieldId: 'revenue', aggregation: 'sum' }],
      filters: [],
    }
    const a = runQuerySync(q)
    const b = runQuerySync(q)
    expect(a.rows).toEqual(b.rows)
  })

  it('crosses two dimensions into series rows', () => {
    const q: SemanticQuery = {
      modelId: 'sm_sales',
      dimensions: [{ fieldId: 'region' }, { fieldId: 'channel' }],
      measures: [{ fieldId: 'revenue', aggregation: 'sum' }],
      filters: [],
    }
    const result = runQuerySync(q)
    expect(result.rows.length).toBeGreaterThan(4)
    expect(result.columns.length).toBe(3)
  })

  it('respects the row limit', () => {
    const q: SemanticQuery = {
      modelId: 'sm_sales',
      dimensions: [{ fieldId: 'city' }],
      measures: [{ fieldId: 'orders', aggregation: 'sum' }],
      filters: [],
      limit: 2,
    }
    expect(runQuerySync(q).rows.length).toBe(2)
  })
})
