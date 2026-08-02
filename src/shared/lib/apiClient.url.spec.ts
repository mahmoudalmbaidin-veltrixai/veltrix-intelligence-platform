import { describe, it, expect } from 'vitest'
import { resolveApiUrl, API_VERSION_PREFIX } from './apiClient'

/**
 * Canonical URL resolution — the ONE rule every adapter path flows through.
 * These lock the behaviour that fixes the Pre-B9 base-URL defect: versioned
 * application routes always resolve under exactly one `/api/v1`, regardless of
 * whether the configured base includes the prefix, while auth/health/absolute
 * URLs pass through untouched.
 */
const HOST = 'http://localhost:8000'
const VERSIONED = 'http://localhost:8000/api/v1'

describe('resolveApiUrl', () => {
  it('exposes the single canonical version prefix', () => {
    expect(API_VERSION_PREFIX).toBe('/api/v1')
  })

  // 1. Host-only base + bare path → adds /api/v1
  it('host-only base + bare path resolves under /api/v1', () => {
    expect(resolveApiUrl(HOST, '/dashboards')).toBe('http://localhost:8000/api/v1/dashboards')
  })

  // 2. Versioned base + bare path → still exactly one /api/v1
  it('versioned base + bare path resolves under a single /api/v1', () => {
    expect(resolveApiUrl(VERSIONED, '/dashboards')).toBe('http://localhost:8000/api/v1/dashboards')
  })

  // 3. Host-only base + already-versioned path → single /api/v1
  it('host-only base + versioned path is not doubled', () => {
    expect(resolveApiUrl(HOST, '/api/v1/dashboards')).toBe('http://localhost:8000/api/v1/dashboards')
  })

  // 4. Versioned base + versioned path → single /api/v1 (no /api/v1/api/v1)
  it('versioned base + versioned path never duplicates the prefix', () => {
    const url = resolveApiUrl(VERSIONED, '/api/v1/dashboards')
    expect(url).toBe('http://localhost:8000/api/v1/dashboards')
    expect(url).not.toContain('/api/v1/api/v1')
  })

  // 5. Trailing slash normalization on the base
  it('normalizes a trailing slash on the base URL', () => {
    expect(resolveApiUrl('http://localhost:8000/', '/datasets')).toBe('http://localhost:8000/api/v1/datasets')
    expect(resolveApiUrl('http://localhost:8000/api/v1/', '/datasets')).toBe('http://localhost:8000/api/v1/datasets')
  })

  // 6. Query parameters are preserved after the resolved path
  it('appends query parameters', () => {
    expect(resolveApiUrl(HOST, '/datasets', { page_size: 100 })).toBe(
      'http://localhost:8000/api/v1/datasets?page_size=100',
    )
    expect(resolveApiUrl(VERSIONED, '/datasets', { page_size: 100 })).toBe(
      'http://localhost:8000/api/v1/datasets?page_size=100',
    )
  })

  // 7. Authentication paths stay unversioned under both base forms
  it('keeps /auth/* unversioned', () => {
    expect(resolveApiUrl(HOST, '/auth/login')).toBe('http://localhost:8000/auth/login')
    expect(resolveApiUrl(VERSIONED, '/auth/login')).toBe('http://localhost:8000/auth/login')
    expect(resolveApiUrl(VERSIONED, '/auth/me')).toBe('http://localhost:8000/auth/me')
    expect(resolveApiUrl(VERSIONED, '/auth/logout')).toBe('http://localhost:8000/auth/logout')
    expect(resolveApiUrl(VERSIONED, '/auth/refresh')).toBe('http://localhost:8000/auth/refresh')
  })

  // 8. Absolute download / external URLs pass through untouched
  it('passes absolute URLs through unchanged', () => {
    const s3 = 'https://cdn.example.com/exports/abc.pdf?sig=xyz'
    expect(resolveApiUrl(HOST, s3)).toBe(s3)
    expect(resolveApiUrl(VERSIONED, 'http://localhost:8000/api/v1/x/download?token=t')).toBe(
      'http://localhost:8000/api/v1/x/download?token=t',
    )
  })

  // 9. SSE / event-stream paths follow the same versioned rule
  it('resolves an event-stream path under /api/v1', () => {
    expect(resolveApiUrl(HOST, '/jobs/123/events')).toBe('http://localhost:8000/api/v1/jobs/123/events')
  })

  // 10. Health / readiness probes stay unversioned if routed through the client
  it('keeps /health and /ready unversioned', () => {
    expect(resolveApiUrl(VERSIONED, '/health')).toBe('http://localhost:8000/health')
    expect(resolveApiUrl(HOST, '/ready')).toBe('http://localhost:8000/ready')
  })

  // 11. Invalid / empty base still yields a version-prefixed relative path
  it('handles an empty base URL (relative, still versioned)', () => {
    expect(resolveApiUrl('', '/dashboards')).toBe('/api/v1/dashboards')
    expect(resolveApiUrl('', '/api/v1/dashboards')).toBe('/api/v1/dashboards')
    expect(resolveApiUrl('', '/auth/login')).toBe('/auth/login')
  })

  // 12. Never produces a duplicated /api/v1 for any versioned combination
  it('never duplicates /api/v1 across base/path combinations', () => {
    const cases = [
      [HOST, '/api/v1/x'],
      [VERSIONED, '/api/v1/x'],
      ['http://localhost:8000/api/v1/', '/api/v1/x'],
      [VERSIONED, '/x'],
    ] as const
    for (const [base, path] of cases) {
      expect(resolveApiUrl(base, path)).not.toContain('/api/v1/api/v1')
    }
  })

  // Signed relative download URL (backend returns /api/v1/...?token=) is preserved
  it('preserves a signed relative download URL with query', () => {
    const signed = '/api/v1/dashboard-exports/42/download?token=abc.def'
    expect(resolveApiUrl(HOST, signed)).toBe('http://localhost:8000/api/v1/dashboard-exports/42/download?token=abc.def')
    expect(resolveApiUrl(VERSIONED, signed)).toBe(
      'http://localhost:8000/api/v1/dashboard-exports/42/download?token=abc.def',
    )
  })

  // Bare path without a leading slash is still normalized
  it('normalizes a path missing its leading slash', () => {
    expect(resolveApiUrl(HOST, 'dashboards' as unknown as string)).toBe('http://localhost:8000/api/v1/dashboards')
  })
})
