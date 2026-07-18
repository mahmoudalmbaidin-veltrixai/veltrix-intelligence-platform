/**
 * Typed, validated environment configuration.
 *
 * Reads `import.meta.env` once, validates it, and exposes a frozen typed config.
 * Fails fast (throws) on invalid combinations rather than silently degrading —
 * e.g. `live` mode without a base URL in production. In development an invalid
 * live config falls back to mock with a loud console warning so the app still
 * boots for local work.
 */

export type ApiMode = 'mock' | 'live'
export type AppEnv = 'development' | 'staging' | 'production'

export interface AppConfig {
  apiMode: ApiMode
  apiBaseUrl: string
  apiTimeoutMs: number
  appEnv: AppEnv
  enableDevtools: boolean
  enableMockLatency: boolean
  isProd: boolean
}

export class EnvConfigError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'EnvConfigError'
  }
}

function parseBool(value: string | undefined, fallback: boolean): boolean {
  if (value == null || value === '') return fallback
  return value === 'true' || value === '1'
}

function parseInt10(value: string | undefined, fallback: number): number {
  const n = Number.parseInt(value ?? '', 10)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

/** Pure builder so it can be unit-tested with arbitrary raw env objects. */
export function buildConfig(raw: Partial<Record<string, string>>): AppConfig {
  const appEnv = (raw.VITE_APP_ENV ?? 'development') as AppEnv
  if (!['development', 'staging', 'production'].includes(appEnv)) {
    throw new EnvConfigError(`Invalid VITE_APP_ENV: "${raw.VITE_APP_ENV}"`)
  }
  const isProd = appEnv === 'production'

  const mode = (raw.VITE_API_MODE ?? 'mock') as ApiMode
  if (mode !== 'mock' && mode !== 'live') {
    throw new EnvConfigError(`Invalid VITE_API_MODE: "${raw.VITE_API_MODE}" (expected "mock" | "live")`)
  }

  const baseUrl = (raw.VITE_API_BASE_URL ?? '').trim()
  let resolvedMode: ApiMode = mode
  if (mode === 'live' && !baseUrl) {
    if (isProd) {
      // Never silently use mock in production when live was intended.
      throw new EnvConfigError('VITE_API_MODE=live requires VITE_API_BASE_URL in production.')
    }
    // Dev/staging: fall back to mock loudly so the app still boots locally.
    console.warn('[env] VITE_API_MODE=live but VITE_API_BASE_URL is empty — falling back to mock mode for local development.')
    resolvedMode = 'mock'
  }

  return Object.freeze({
    apiMode: resolvedMode,
    apiBaseUrl: baseUrl,
    apiTimeoutMs: parseInt10(raw.VITE_API_TIMEOUT_MS, 20_000),
    appEnv,
    enableDevtools: parseBool(raw.VITE_ENABLE_DEVTOOLS, !isProd),
    enableMockLatency: parseBool(raw.VITE_ENABLE_MOCK_LATENCY, true),
    isProd,
  })
}

export const config: AppConfig = buildConfig(import.meta.env as Partial<Record<string, string>>)

export const isMock = () => config.apiMode === 'mock'
export const isLive = () => config.apiMode === 'live'
