/**
 * Maps any thrown value to a safe, user-facing message for lifecycle/destructive
 * actions. Only backend-contract fields (message/detail/code/correlationId) are
 * surfaced — never stack traces, SQL, secrets or internal paths.
 */
import { ApiError } from '@/shared/types/api'

export interface SafeError {
  message: string
  code?: string
  correlationId?: string
  kind?: string
}

export function toSafeError(e: unknown): SafeError {
  if (e instanceof ApiError) {
    // ApiError.message carries the backend-provided detail when present, else a
    // normalized status text; fall back to the friendly per-kind message.
    const message = e.message && e.message !== e.kind ? e.message : e.friendlyMessage
    return { message, code: e.code, correlationId: e.correlationId, kind: e.kind }
  }
  if (e instanceof Error && e.message) return { message: e.message }
  return { message: 'Something went wrong. Please try again.' }
}

/** Convenience: a single display string including the error code when present. */
export function safeErrorText(e: unknown): string {
  const s = toSafeError(e)
  return s.code ? `${s.message} (${s.code})` : s.message
}
