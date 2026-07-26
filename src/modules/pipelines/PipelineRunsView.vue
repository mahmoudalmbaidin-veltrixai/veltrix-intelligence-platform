<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { pipelineService } from './pipelines.service'
import type { PipelineRun } from '@/shared/types/pipeline'
import { relativeTime, formatDuration, formatNumber } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const route = useRoute()
const router = useRouter()
const id = route.params.id as string
const runs = ref<PipelineRun[]>([])
const selected = ref<PipelineRun | null>(null)
const loading = ref(true)

async function loadRuns() {
  loading.value = true
  runs.value = await pipelineService.listRuns(id)
  loading.value = false
}
async function retrySelected() {
  if (!selected.value) return
  selected.value = await pipelineService.retryRun(id, selected.value.id)
  await loadRuns()
}
async function cancelSelected() {
  if (!selected.value) return
  selected.value = await pipelineService.cancelRun(id, selected.value.id)
  await loadRuns()
}
async function copyDiagnostics() {
  if (!selected.value) return
  await navigator.clipboard.writeText(
    `Run ${selected.value.id}\nCorrelation ID: ${selected.value.correlationId}\nStatus: ${selected.value.status}`,
  )
}
onMounted(loadRuns)

const columns: Column<PipelineRun>[] = [
  { key: 'status', label: 'Status' },
  { key: 'trigger', label: 'Trigger' },
  { key: 'startedAt', label: 'Started' },
  { key: 'durationMs', label: 'Duration' },
  { key: 'rowsProcessed', label: 'Rows', align: 'right' },
  { key: 'correlationId', label: 'Correlation ID' },
]
function tone(s: string) {
  return s === 'succeeded' ? 'success' : s === 'failed' ? 'danger' : s === 'running' ? 'info' : 'neutral'
}
</script>

<template>
  <div>
    <VipPageHeader title="Pipeline runs" description="Execution history, status and diagnostics.">
      <template #actions>
        <VipButton variant="tertiary" icon="chevronLeft" @click="router.push(`/pipelines/${id}`)"
          >Open in studio</VipButton
        >
      </template>
    </VipPageHeader>

    <p v-if="loading" aria-live="polite">Loading run historyâ€¦</p>
    <VipTable
      v-else
      :columns="columns"
      :rows="runs"
      :row-key="(r) => r.id"
      clickable
      @row-click="(r) => (selected = r)"
    >
      <template #cell-status="{ row }"
        ><VipBadge :tone="tone(row.status)" size="sm">{{ row.status }}</VipBadge></template
      >
      <template #cell-startedAt="{ row }">{{ relativeTime(row.startedAt) }}</template>
      <template #cell-durationMs="{ row }">{{ formatDuration(row.durationMs) }}</template>
      <template #cell-rowsProcessed="{ row }">{{ formatNumber(row.rowsProcessed, { style: 'compact' }) }}</template>
      <template #cell-correlationId="{ row }"
        ><span class="rn-cid">{{ row.correlationId }}</span></template
      >
    </VipTable>

    <VipDrawer :open="!!selected" :title="`Run ${selected?.correlationId}`" :width="480" @close="selected = null">
      <template v-if="selected">
        <div class="rn-facts">
          <div class="rn-fact">
            <span>Status</span><VipBadge :tone="tone(selected.status)" size="sm">{{ selected.status }}</VipBadge>
          </div>
          <div class="rn-fact"><span>Trigger</span>{{ selected.trigger }}</div>
          <div class="rn-fact"><span>Started</span>{{ relativeTime(selected.startedAt) }}</div>
          <div class="rn-fact"><span>Duration</span>{{ formatDuration(selected.durationMs) }}</div>
          <div class="rn-fact"><span>Rows processed</span>{{ formatNumber(selected.rowsProcessed) }}</div>
          <div class="rn-fact"><span>Attempt</span>{{ selected.attempt }}</div>
          <div class="rn-fact"><span>Progress</span>{{ selected.progress }}%</div>
          <div class="rn-fact">
            <span>Correlation ID</span><span class="rn-cid">{{ selected.correlationId }}</span>
          </div>
        </div>
        <div class="rn-actions">
          <VipButton
            v-if="selected.status === 'failed'"
            variant="secondary"
            size="sm"
            icon="refresh"
            @click="retrySelected"
            >Retry run</VipButton
          >
          <VipButton
            v-if="['queued', 'running', 'waiting'].includes(selected.status)"
            variant="danger"
            size="sm"
            icon="close"
            @click="cancelSelected"
            >Cancel</VipButton
          >
          <VipButton variant="tertiary" size="sm" icon="copy" @click="copyDiagnostics">Copy diagnostics</VipButton>
        </div>
      </template>
    </VipDrawer>
  </div>
</template>

<style scoped>
.rn-cid {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.rn-facts {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.rn-fact {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--vip-sp-4) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
  font-size: var(--vip-fs-sm);
}
.rn-fact span:first-child {
  color: var(--vip-text-muted);
}
.rn-actions {
  display: flex;
  gap: var(--vip-sp-4);
  margin-top: var(--vip-sp-6);
}
</style>
