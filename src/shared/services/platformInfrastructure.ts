/** Live B8 jobs, secure files, and real-time event API adapter. */

import { apiClient, type ServerEvent } from '@/shared/lib/apiClient'
import { ApiError } from '@/shared/types/api'

const API = '/api/v1'

export interface JobProgress {
  percent: number
  completed_steps: number
  total_steps: number | null
  stage: string | null
  message: string | null
  estimated_completion_at: string | null
}

export interface PlatformJob {
  id: string
  type: string
  name: string
  status: string
  queue: string
  priority: number
  attempt: number
  max_attempts: number
  progress: JobProgress
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
  cancellation_requested: boolean
}

export interface PlatformFile {
  id: string
  filename: string
  original_filename: string
  mime_type: string
  extension: string
  size_bytes: number
  sha256: string | null
  kind: string
  status: string
  tags: string[]
  current_version: number
  created_at: string
  updated_at: string
}

export interface DeadLetterJob {
  id: string
  job_id: string
  failure_reason: string
  last_error_code: string
  attempt_count: number
  status: string
  created_at: string
}

function eventId(value: string): [number, number] {
  const [milliseconds, sequence] = value.split('-', 2)
  return [Number(milliseconds) || 0, Number(sequence) || 0]
}

function after(left: string, right: string): boolean {
  const a = eventId(left)
  const b = eventId(right)
  return a[0] > b[0] || (a[0] === b[0] && a[1] > b[1])
}

function uploadContentType(file: File): string {
  const extension = file.name.split('.').pop()?.toLowerCase()
  const known: Record<string, string> = {
    csv: 'text/csv',
    json: 'application/json',
    pdf: 'application/pdf',
    png: 'image/png',
  }
  return known[extension ?? ''] ?? (file.type || 'application/octet-stream')
}

async function abortableDelay(milliseconds: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) return
  await new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, milliseconds)
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer)
        resolve()
      },
      { once: true },
    )
  })
}

export const platformInfrastructure = {
  jobs: (query?: { status?: string; before?: string; limit?: number }) =>
    apiClient.get<{ items: PlatformJob[]; next_cursor: string | null }>(`${API}/jobs`, { query }),
  job: (id: string) => apiClient.get<PlatformJob>(`${API}/jobs/${id}`),
  progress: (id: string) => apiClient.get<PlatformJob>(`${API}/jobs/${id}/progress`),
  logs: (id: string) => apiClient.get(`${API}/jobs/${id}/logs`),
  cancel: (id: string) => apiClient.post<PlatformJob>(`${API}/jobs/${id}/cancel`),
  retry: (id: string) => apiClient.post<PlatformJob>(`${API}/jobs/${id}/retry`),
  deadLetters: () => apiClient.get<DeadLetterJob[]>(`${API}/jobs/dead-letters`),
  discardDeadLetter: (id: string) => apiClient.post<DeadLetterJob>(`${API}/jobs/dead-letters/${id}/discard`),
  files: (query?: { before?: string; limit?: number }) =>
    apiClient.get<{ items: PlatformFile[]; next_cursor: string | null }>(`${API}/files`, {
      query,
    }),
  upload: (file: File) =>
    apiClient.uploadRaw<PlatformFile>(`${API}/files`, file, {
      headers: { 'Content-Type': uploadContentType(file), 'X-File-Name': file.name },
    }),
  replace: (id: string, file: File) =>
    apiClient.put<PlatformFile>(`${API}/files/${id}/content`, undefined, {
      rawBody: file,
      headers: { 'Content-Type': uploadContentType(file), 'X-File-Name': file.name },
    }),
  versions: (id: string) => apiClient.get(`${API}/files/${id}/versions`),
  restore: (id: string, version: number) =>
    apiClient.post<PlatformFile>(`${API}/files/${id}/versions/${version}/restore`),
  remove: (id: string) => apiClient.delete<void>(`${API}/files/${id}`),
  download: async (id: string) => {
    const link = await apiClient.post<{ url: string }>(`${API}/files/${id}/download`)
    return apiClient.downloadWithMetadata(link.url)
  },
  events: (
    types: string[],
    options: { lastEventId?: string; signal?: AbortSignal } = {},
  ): AsyncGenerator<ServerEvent<Record<string, unknown>>> =>
    apiClient.eventStream<Record<string, unknown>>(`${API}/events/stream`, {
      query: { types },
      signal: options.signal,
      headers: options.lastEventId ? { 'Last-Event-ID': options.lastEventId } : undefined,
    }),
  async *resilientEvents(
    types: string[],
    options: {
      scope: string
      lastEventId?: string
      signal?: AbortSignal
      onConnectionChange?: (connected: boolean) => void
    },
  ): AsyncGenerator<ServerEvent<Record<string, unknown>>> {
    const storageKey = `vip.events.cursor:${options.scope}`
    let cursor = options.lastEventId ?? sessionStorage.getItem(storageKey) ?? undefined
    let reconnectDelay = 1_000
    while (!options.signal?.aborted) {
      try {
        options.onConnectionChange?.(true)
        for await (const event of this.events(types, {
          lastEventId: cursor,
          signal: options.signal,
        })) {
          if (options.signal?.aborted) return
          if (event.id && cursor && !after(event.id, cursor) && event.type !== 'stream.replay_gap') continue
          if (event.id) {
            cursor = event.id
            sessionStorage.setItem(storageKey, cursor)
          }
          reconnectDelay = 1_000
          yield event
        }
      } catch (error) {
        if (options.signal?.aborted) return
        const apiError = ApiError.from(error)
        if (['unauthorized', 'forbidden', 'validation', 'not-found'].includes(apiError.kind)) throw apiError
      } finally {
        options.onConnectionChange?.(false)
      }
      await abortableDelay(reconnectDelay, options.signal)
      reconnectDelay = Math.min(30_000, reconnectDelay * 2)
    }
  },
}
