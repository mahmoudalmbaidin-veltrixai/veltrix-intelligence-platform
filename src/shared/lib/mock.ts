/**
 * Mock backend infrastructure.
 *
 * `latency()` simulates realistic network delay. `maybeFail()` can inject
 * error scenarios for demos. `LocalStore` is a typed, namespaced persistence
 * adapter backed by localStorage — the editors use it so canvas/dashboard
 * state survives reloads. Secrets are NEVER written here (see NOTE below).
 */
import { ApiError, type ApiErrorKind } from '@/shared/types/api'

let seed = 1
/** Deterministic PRNG so mock data is stable across reloads/tests. */
export function rng(): number {
  seed = (seed * 1103515245 + 12345) & 0x7fffffff
  return seed / 0x7fffffff
}
export function resetRng(s = 1) {
  seed = s
}

export function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(rng() * arr.length)]
}
export function randInt(min: number, max: number): number {
  return Math.floor(rng() * (max - min + 1)) + min
}

export function latency(min = 180, max = 520): Promise<void> {
  const ms = min + Math.round(Math.random() * (max - min))
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function fail(kind: ApiErrorKind, message: string, detail?: string): never {
  throw new ApiError(kind, message, { detail })
}

/**
 * Typed namespaced localStorage adapter. Used only for non-sensitive editor
 * state and UI preferences. Do not persist credentials/secrets here.
 */
export class LocalStore<T> {
  constructor(private readonly key: string) {}

  read(fallback: T): T {
    try {
      const raw = localStorage.getItem(this.key)
      if (raw == null) return fallback
      return JSON.parse(raw) as T
    } catch {
      return fallback
    }
  }

  write(value: T): void {
    try {
      localStorage.setItem(this.key, JSON.stringify(value))
    } catch {
      /* quota / unavailable — non-fatal for mock persistence */
    }
  }

  clear(): void {
    localStorage.removeItem(this.key)
  }
}

/**
 * Deep clone via JSON. Unlike structuredClone this safely strips Vue reactive
 * proxies (which structuredClone rejects) — our domain objects are plain data.
 */
export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function nowIso(): string {
  return new Date().toISOString()
}

export function isoAgo(mins: number): string {
  return new Date(Date.now() - mins * 60_000).toISOString()
}

export function isoAhead(mins: number): string {
  return new Date(Date.now() + mins * 60_000).toISOString()
}
