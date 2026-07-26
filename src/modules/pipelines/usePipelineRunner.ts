/** Polling adapter for durable asynchronous B7 runs. */
import { computed, onScopeDispose, ref } from 'vue'
import { pipelineService } from './pipelines.service'
import type { PipelineRun } from '@/shared/types/pipeline'

export function usePipelineRunner() {
  const run = ref<PipelineRun | null>(null)
  const isRunning = computed(() => ['queued', 'running', 'waiting'].includes(run.value?.status ?? ''))
  let timer: number | undefined
  function stop() {
    if (timer) window.clearInterval(timer)
    timer = undefined
  }
  async function refresh() {
    if (!run.value) return
    run.value = await pipelineService.getRun(run.value.pipelineId, run.value.id)
    if (!isRunning.value) stop()
  }
  async function start(pipelineId: string) {
    stop()
    run.value = await pipelineService.startRun(pipelineId)
    timer = window.setInterval(() => void refresh(), 1000)
  }
  async function cancel() {
    if (!run.value) return
    run.value = await pipelineService.cancelRun(run.value.pipelineId, run.value.id)
    await refresh()
  }
  async function retry() {
    if (!run.value) return
    run.value = await pipelineService.retryRun(run.value.pipelineId, run.value.id)
    timer = window.setInterval(() => void refresh(), 1000)
  }
  onScopeDispose(stop)
  return { run, isRunning, start, cancel, retry, refresh }
}
