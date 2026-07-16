/**
 * Minimal typed server-state layer (query + mutation) with caching,
 * dedup, cancellation, retry and invalidation. Deliberately dependency-free
 * so it can be swapped for TanStack Query later without changing call sites.
 */
import { ref, shallowRef, watch, onScopeDispose, type Ref } from 'vue'
import { ApiError } from '@/shared/types/api'

interface CacheEntry {
  data: unknown
  ts: number
  inflight?: Promise<unknown>
}

const cache = new Map<string, CacheEntry>()
const listeners = new Map<string, Set<() => void>>()

const DEFAULT_STALE = 15_000

function notify(prefix: string) {
  for (const [key, set] of listeners) {
    if (key.startsWith(prefix)) set.forEach((fn) => fn())
  }
}

/** Invalidate any cache key beginning with the given prefix. */
export function invalidateQueries(prefix: string) {
  for (const key of [...cache.keys()]) {
    if (key.startsWith(prefix)) cache.delete(key)
  }
  notify(prefix)
}

export interface UseQueryOptions {
  staleTime?: number
  retry?: number
  enabled?: Ref<boolean> | boolean
}

export interface UseQueryResult<T> {
  data: Ref<T | undefined>
  error: Ref<ApiError | undefined>
  isLoading: Ref<boolean>
  isFetching: Ref<boolean>
  refetch: () => Promise<void>
}

export function useQuery<T>(
  key: string | (() => string),
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: UseQueryOptions = {},
): UseQueryResult<T> {
  // Accept a static string key or a reactive getter.
  const keyGetter: () => string = typeof key === 'function' ? key : () => key
  const data = shallowRef<T | undefined>(undefined)
  const error = ref<ApiError | undefined>(undefined)
  const isLoading = ref(true)
  const isFetching = ref(false)
  const staleTime = options.staleTime ?? DEFAULT_STALE
  const retry = options.retry ?? 1

  let controller: AbortController | undefined
  let currentKey = ''

  const enabled = () =>
    typeof options.enabled === 'boolean'
      ? options.enabled
      : options.enabled?.value ?? true

  async function run(force = false) {
    if (!enabled()) {
      isLoading.value = false
      return
    }
    const key = keyGetter()
    currentKey = key
    const cached = cache.get(key)
    if (cached && !force && Date.now() - cached.ts < staleTime) {
      data.value = cached.data as T
      error.value = undefined
      isLoading.value = false
      return
    }
    if (cached?.inflight) {
      await cached.inflight
      if (currentKey === key) {
        data.value = cache.get(key)?.data as T
        isLoading.value = false
      }
      return
    }

    controller?.abort()
    controller = new AbortController()
    const signal = controller.signal
    isFetching.value = true
    if (data.value === undefined) isLoading.value = true

    const attempt = async (n: number): Promise<T> => {
      try {
        return await fetcher(signal)
      } catch (e) {
        if (signal.aborted) throw e
        const apiErr = e instanceof ApiError ? e : new ApiError('server', String(e))
        if (n < retry && apiErr.kind !== 'forbidden' && apiErr.kind !== 'validation') {
          await new Promise((r) => setTimeout(r, 200 * (n + 1)))
          return attempt(n + 1)
        }
        throw apiErr
      }
    }

    const promise = attempt(0)
    cache.set(key, { data: cached?.data, ts: cached?.ts ?? 0, inflight: promise })

    try {
      const result = await promise
      if (signal.aborted) return
      cache.set(key, { data: result, ts: Date.now() })
      if (currentKey === key) {
        data.value = result
        error.value = undefined
      }
    } catch (e) {
      if (signal.aborted) return
      const c = cache.get(key)
      if (c) c.inflight = undefined
      if (currentKey === key) error.value = e as ApiError
    } finally {
      if (currentKey === key) {
        isFetching.value = false
        isLoading.value = false
      }
    }
  }

  const relisten = () => {
    const key = keyGetter()
    const set = listeners.get(key) ?? new Set()
    const cb = () => run(true)
    set.add(cb)
    listeners.set(key, set)
    return () => set.delete(cb)
  }

  let unlisten = relisten()

  watch(keyGetter, () => {
    unlisten()
    unlisten = relisten()
    run()
  })

  if (typeof options.enabled !== 'boolean' && options.enabled) {
    watch(options.enabled, (v) => v && run())
  }

  onScopeDispose(() => {
    controller?.abort()
    unlisten()
  })

  run()

  return { data, error, isLoading, isFetching, refetch: () => run(true) }
}

export interface UseMutationOptions<TArgs, TData> {
  onSuccess?: (data: TData, args: TArgs) => void
  onError?: (error: ApiError, args: TArgs) => void
  invalidate?: string[]
}

export interface UseMutationResult<TArgs, TData> {
  mutate: (args: TArgs) => Promise<TData>
  isPending: Ref<boolean>
  error: Ref<ApiError | undefined>
  data: Ref<TData | undefined>
}

export function useMutation<TArgs, TData>(
  fn: (args: TArgs) => Promise<TData>,
  options: UseMutationOptions<TArgs, TData> = {},
): UseMutationResult<TArgs, TData> {
  const isPending = ref(false)
  const error = ref<ApiError | undefined>(undefined)
  const data = shallowRef<TData | undefined>(undefined)

  async function mutate(args: TArgs): Promise<TData> {
    isPending.value = true
    error.value = undefined
    try {
      const result = await fn(args)
      data.value = result
      options.invalidate?.forEach((p) => invalidateQueries(p))
      options.onSuccess?.(result, args)
      return result
    } catch (e) {
      const apiErr = e instanceof ApiError ? e : new ApiError('server', String(e))
      error.value = apiErr
      options.onError?.(apiErr, args)
      throw apiErr
    } finally {
      isPending.value = false
    }
  }

  return { mutate, isPending, error, data }
}
