import { describe, it, expect } from 'vitest'
import { resolveApiUrl } from './apiClient'

// Import the real service modules so a path/type regression in any adapter also
// breaks this suite (compile-time coverage of the modules under test).
import '@/modules/dashboards/dashboards.service'
import '@/modules/datasets/datasets.service'
import '@/modules/semantic/semantic.service'
import '@/modules/home/home.service'
import '@/modules/operations/operations.service'

/**
 * Service-level guard for the Pre-B9 base-URL fix: the *actual* endpoint paths
 * used by the Dashboard, Dataset, Semantic, Home and Audit adapters must resolve
 * to exactly one `/api/v1`, whether the deployment configures the base as the
 * bare host or with the version prefix already included.
 *
 * Paths mirror the live adapters:
 *   dashboards.service.ts   → GET /dashboards, GET /dashboards/{id}/editor
 *   datasets.service.ts     → GET /datasets
 *   semantic.service.ts     → GET /semantic-models
 *   home.service.ts         → GET /home/summary
 *   operations.service.ts   → GET /audit
 */
const HOST = 'http://localhost:8000'
const VERSIONED = 'http://localhost:8000/api/v1'

const MODULE_ENDPOINTS: Array<{ module: string; path: string; expected: string }> = [
  { module: 'dashboard-list', path: '/dashboards', expected: '/api/v1/dashboards' },
  {
    module: 'dashboard-editor',
    path: '/dashboards/abc/editor',
    expected: '/api/v1/dashboards/abc/editor',
  },
  { module: 'dataset-list', path: '/datasets', expected: '/api/v1/datasets' },
  { module: 'semantic-models', path: '/semantic-models', expected: '/api/v1/semantic-models' },
  { module: 'home-summary', path: '/home/summary', expected: '/api/v1/home/summary' },
  { module: 'audit', path: '/audit', expected: '/api/v1/audit' },
]

describe('service adapter URL resolution (single /api/v1)', () => {
  for (const { module, path, expected } of MODULE_ENDPOINTS) {
    it(`${module} resolves under one /api/v1 with a host-only base`, () => {
      const url = resolveApiUrl(HOST, path)
      expect(url).toBe(`${HOST}${expected}`)
      expect(url.match(/\/api\/v1/g)?.length).toBe(1)
    })

    it(`${module} resolves under one /api/v1 with a versioned base`, () => {
      const url = resolveApiUrl(VERSIONED, path)
      expect(url).toBe(`${HOST}${expected}`)
      expect(url).not.toContain('/api/v1/api/v1')
    })
  }

  it('audit keeps its query string under both base forms', () => {
    const q = { search: 'x', result: 'denied' }
    expect(resolveApiUrl(HOST, '/audit', q)).toBe(`${HOST}/api/v1/audit?search=x&result=denied`)
    expect(resolveApiUrl(VERSIONED, '/audit', q)).toBe(`${HOST}/api/v1/audit?search=x&result=denied`)
  })
})
