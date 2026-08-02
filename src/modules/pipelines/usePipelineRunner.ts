/** Bounded, visibility-aware polling adapter for durable asynchronous B7 runs. */
import { computed, onScopeDispose, ref } from 'vue'
import { pipelineService } from './pipelines.service'
import type { PipelineRun } from '@/shared/types/pipeline'

const INITIAL_DELAY_MS = 1_000
const MAX_DELAY_MS = 10_000
const HIDDEN_DELAY_MS = 5_000
const POLLING_TIMEOUT_MS = 15 * 60_000

export function usePipelineRunner() {
  const run = ref<PipelineRun | null>(null)
  const pollingTimedOut = ref(false)
  const isRunning = computed(() => ['queued', 'running', 'waiting'].includes(run.value?.status ?? ''))
  let timer: number | undefined
  let requestController: AbortController | undefined
  let nextDelay = INITIAL_DELAY_MS
  let deadline = 0

  function stop() {
    if (timer !== undefined) window.clearTimeout(timer)
    timer = undefined
    requestController?.abort()
    requestController = undefined
  }

  function schedule(delay = nextDelay) {
    if (!isRunning.value || pollingTimedOut.value) return
    if (timer !== undefined) window.clearTimeout(timer)
    timer = window.setTimeout(() => void poll(), delay)
  }

  async function refresh(signal?: AbortSignal) {
    if (!run.value) return
    run.value = await pipelineService.getRun(run.value.pipelineId, run.value.id, signal)
    if (!isRunning.value) stop()
  }

  async function poll() {
    timer = undefined
    if (!isRunning.value) return
    if (Date.now() >= deadline) {
      pollingTimedOut.value = true
      stop()
      return
    }
    if (document.hidden) {
      schedule(HIDDEN_DELAY_MS)
      return
    }
    const controller = new AbortController()
    requestController = controller
    try {
      await refresh(controller.signal)
      nextDelay = INITIAL_DELAY_MS
    } catch {
      if (!controller.signal.aborted) {
        nextDelay = Math.min(nextDelay * 2, MAX_DELAY_MS)
      }
    } finally {
      if (requestController === controller) requestController = undefined
    }
    schedule()
  }

  function beginPolling() {
    stop()
    pollingTimedOut.value = false
    nextDelay = INITIAL_DELAY_MS
    deadline = Date.now() + POLLING_TIMEOUT_MS
    schedule()
  }

  async function start(pipelineId: string) {
    stop()
    run.value = await pipelineService.startRun(pipelineId)
    beginPolling()
  }

  async function cancel() {
    if (!run.value) return
    stop()
    run.value = await pipelineService.cancelRun(run.value.pipelineId, run.value.id)
    await refresh()
  }

  async function retry() {
    if (!run.value) return
    run.value = await pipelineService.retryRun(run.value.pipelineId, run.value.id)
    beginPolling()
  }

  function visibilityChanged() {
    if (!document.hidden && isRunning.value) schedule(0)
  }

  document.addEventListener('visibilitychange', visibilityChanged)
  onScopeDispose(() => {
    stop()
    document.removeEventListener('visibilitychange', visibilityChanged)
  })
  return { run, isRunning, pollingTimedOut, start, cancel, retry, refresh }
}
