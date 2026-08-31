import { describe, it, expect } from 'vitest'
import { buildConfig, EnvConfigError } from './env'

describe('env config', () => {
  it('defaults to mock mode with sane values', () => {
    const c = buildConfig({})
    expect(c.apiMode).toBe('mock')
    expect(c.apiTimeoutMs).toBe(20_000)
    expect(c.appEnv).toBe('development')
    expect(c.enableMockLatency).toBe(true)
  })

  it('parses live mode with a base url', () => {
    const c = buildConfig({ VITE_API_MODE: 'live', VITE_API_BASE_URL: 'https://api.x.com', VITE_APP_ENV: 'production' })
    expect(c.apiMode).toBe('live')
    expect(c.apiBaseUrl).toBe('https://api.x.com')
    expect(c.isProd).toBe(true)
  })

  it('supports an explicit demo build through the same-origin proxy', () => {
    const c = buildConfig({ VITE_API_MODE: 'live', VITE_API_BASE_URL: '/', VITE_APP_ENV: 'demo' })
    expect(c.apiMode).toBe('live')
    expect(c.apiBaseUrl).toBe('/')
    expect(c.enableDevtools).toBe(false)
    expect(c.isProd).toBe(false)
  })

  it('falls back to mock in dev ONLY with the explicit opt-in flag', () => {
    const c = buildConfig({ VITE_API_MODE: 'live', VITE_APP_ENV: 'development', VITE_ALLOW_MOCK_FALLBACK: 'true' })
    expect(c.apiMode).toBe('mock')
  })

  it('fails closed in dev without the opt-in flag', () => {
    expect(() => buildConfig({ VITE_API_MODE: 'live', VITE_APP_ENV: 'development' })).toThrow(EnvConfigError)
  })

  it('fails closed in staging even with the opt-in flag (no silent mock)', () => {
    expect(() =>
      buildConfig({ VITE_API_MODE: 'live', VITE_APP_ENV: 'staging', VITE_ALLOW_MOCK_FALLBACK: 'true' }),
    ).toThrow(EnvConfigError)
  })

  it('throws in production when live has no base url', () => {
    expect(() => buildConfig({ VITE_API_MODE: 'live', VITE_APP_ENV: 'production' })).toThrow(EnvConfigError)
  })

  it('rejects mock services in demo, staging and production', () => {
    expect(() =>
      buildConfig({ VITE_APP_ENV: 'demo', VITE_API_MODE: 'mock', VITE_API_BASE_URL: 'https://api.x.com' }),
    ).toThrow(EnvConfigError)
    expect(() =>
      buildConfig({ VITE_APP_ENV: 'staging', VITE_API_MODE: 'mock', VITE_API_BASE_URL: 'https://api.x.com' }),
    ).toThrow(EnvConfigError)
    expect(() =>
      buildConfig({ VITE_APP_ENV: 'production', VITE_API_MODE: 'mock', VITE_API_BASE_URL: 'https://api.x.com' }),
    ).toThrow(EnvConfigError)
  })

  it('rejects an invalid API mode', () => {
    expect(() => buildConfig({ VITE_API_MODE: 'bogus' })).toThrow(EnvConfigError)
  })

  it('rejects an invalid app env', () => {
    expect(() => buildConfig({ VITE_APP_ENV: 'nope' })).toThrow(EnvConfigError)
  })

  it('rejects invalid or unsafe live base URLs', () => {
    expect(() => buildConfig({ VITE_API_MODE: 'live', VITE_API_BASE_URL: 'api.internal' })).toThrow(EnvConfigError)
    expect(() => buildConfig({ VITE_API_MODE: 'live', VITE_API_BASE_URL: 'javascript:alert(1)' })).toThrow(
      EnvConfigError,
    )
  })

  it('parses numeric timeout and boolean flags', () => {
    const c = buildConfig({ VITE_API_TIMEOUT_MS: '5000', VITE_ENABLE_MOCK_LATENCY: 'false' })
    expect(c.apiTimeoutMs).toBe(5000)
    expect(c.enableMockLatency).toBe(false)
  })
})
