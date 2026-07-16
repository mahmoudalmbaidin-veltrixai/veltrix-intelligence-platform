/**
 * Simulated pipeline execution. Advances nodes in topological order, emitting
 * live status/log/row-count updates — mirrors what a real orchestration
 * backend would stream over websockets.
 *
 * INTEGRATION POINT: replace the timer loop with an EventSource/WebSocket
 * subscription to /api/v1/pipelines/:id/runs/:runId/events.
 */
import { ref, computed, onScopeDispose } from 'vue'
import type { Pipeline, PipelineRun, RunLogEntry, RunNodeState } from '@/shared/types/pipeline'
import { createRun } from './pipelines.service'
import { NODE_TYPES } from './nodeTypes'

function topoOrder(pipeline: Pipeline): string[] {
  const indeg = new Map<string, number>()
  pipeline.nodes.forEach((n) => indeg.set(n.id, 0))
  pipeline.edges.forEach((e) => indeg.set(e.targetNode, (indeg.get(e.targetNode) ?? 0) + 1))
  const queue = [...indeg.entries()].filter(([, d]) => d === 0).map(([id]) => id)
  const order: string[] = []
  const seen = new Set<string>()
  while (queue.length) {
    const id = queue.shift()!
    if (seen.has(id)) continue
    seen.add(id)
    order.push(id)
    pipeline.edges.filter((e) => e.sourceNode === id).forEach((e) => {
      const d = (indeg.get(e.targetNode) ?? 1) - 1
      indeg.set(e.targetNode, d)
      if (d <= 0) queue.push(e.targetNode)
    })
  }
  // include any orphans
  pipeline.nodes.forEach((n) => { if (!seen.has(n.id)) order.push(n.id) })
  return order
}

export function usePipelineRunner() {
  const run = ref<PipelineRun | null>(null)
  const isRunning = computed(() => run.value?.status === 'running' || run.value?.status === 'queued')
  let timer: number | undefined
  let cancelled = false

  function stop() {
    if (timer) window.clearInterval(timer)
    timer = undefined
  }

  function log(entry: Omit<RunLogEntry, 'ts'>) {
    if (!run.value) return
    run.value.logs.push({ ...entry, ts: new Date().toISOString() })
  }

  function start(pipeline: Pipeline, opts: { trigger?: PipelineRun['trigger']; failNode?: string; attempt?: number } = {}) {
    stop()
    cancelled = false
    const r = createRun(pipeline, opts.trigger ?? 'manual', opts.attempt ?? 1)
    run.value = r
    const order = topoOrder(pipeline).filter((id) => pipeline.nodes.some((n) => n.id === id))
    let idx = -1
    const started = Date.now()

    r.status = 'running'
    log({ level: 'info', message: `Execution started · ${order.length} nodes` })

    timer = window.setInterval(() => {
      if (!run.value || cancelled) return

      // finalize previous running node
      if (idx >= 0 && idx < order.length) {
        const prevId = order[idx]
        const st = run.value.nodeStates.find((s) => s.nodeId === prevId)!
        if (opts.failNode && prevId === opts.failNode) {
          st.status = 'failed'
          st.message = 'Runtime error: null key in join'
          log({ level: 'error', nodeId: prevId, message: `${nodeTitle(pipeline, prevId)} failed — null key in join condition` })
          run.value.status = 'failed'
          run.value.finishedAt = new Date().toISOString()
          run.value.durationMs = Date.now() - started
          stop()
          return
        }
        st.status = 'succeeded'
        st.rows = Math.round(200_000 + Math.random() * 2_000_000)
        st.durationMs = Math.round(1500 + Math.random() * 6000)
        run.value.rowsProcessed += st.rows
        log({ level: 'info', nodeId: prevId, message: `${nodeTitle(pipeline, prevId)} ✓ ${st.rows.toLocaleString()} rows in ${(st.durationMs / 1000).toFixed(1)}s` })
      }

      idx += 1
      if (idx >= order.length) {
        run.value.status = 'succeeded'
        run.value.progress = 100
        run.value.currentNodeId = undefined
        run.value.finishedAt = new Date().toISOString()
        run.value.durationMs = Date.now() - started
        log({ level: 'info', message: `Execution succeeded · ${run.value.rowsProcessed.toLocaleString()} rows processed` })
        stop()
        return
      }

      const id = order[idx]
      const st = run.value.nodeStates.find((s) => s.nodeId === id)!
      st.status = 'running'
      run.value.currentNodeId = id
      run.value.progress = Math.round((idx / order.length) * 100)
      log({ level: 'info', nodeId: id, message: `${nodeTitle(pipeline, id)} started (${NODE_TYPES[pipeline.nodes.find((n) => n.id === id)!.kind].label})` })
    }, 900)
  }

  function cancel() {
    if (!run.value) return
    cancelled = true
    run.value.nodeStates.forEach((s: RunNodeState) => {
      if (s.status === 'running' || s.status === 'queued') s.status = 'cancelled'
    })
    run.value.status = 'cancelled'
    run.value.finishedAt = new Date().toISOString()
    log({ level: 'warn', message: 'Run cancelled by user' })
    stop()
  }

  function nodeTitle(pipeline: Pipeline, id: string): string {
    return pipeline.nodes.find((n) => n.id === id)?.title ?? id
  }

  onScopeDispose(stop)

  return { run, isRunning, start, cancel }
}
