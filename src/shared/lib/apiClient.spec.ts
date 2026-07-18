import { describe, it, expect } from 'vitest'
import { apiClient } from './apiClient'

describe('apiClient query building', () => {
  it('serializes scalars and arrays, dropping nullish', () => {
    const q = apiClient._buildQuery({ page: 2, search: 'x y', active: true, skip: undefined, tags: ['a', 'b'] })
    expect(q).toContain('page=2')
    expect(q).toContain('active=true')
    expect(q).toContain('search=x+y')
    expect(q).toContain('tags=a')
    expect(q).toContain('tags=b')
    expect(q).not.toContain('skip')
  })

  it('returns an empty string for no query', () => {
    expect(apiClient._buildQuery(undefined)).toBe('')
  })

  it('exposes status→kind mapping', () => {
    expect(apiClient._statusToKind(404)).toBe('not-found')
  })
})
