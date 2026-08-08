<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { pipelineService } from './pipelines.service'
import { usePipelinePermissions } from './usePipelinePermissions'
import type { Pipeline, PipelineArtifact, PipelineRun } from '@/shared/types/pipeline'
import { ApiError } from '@/shared/types/api'
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
const pipeline = ref<Pipeline | undefined>()
const artifacts = ref<PipelineArtifact[]>([])
const artifactsLoading = ref(false)
const artifactsError = ref<string | null>(null)
const downloadingId = ref<string | null>(null)

const perms = usePipelinePermissions(computed(() => pipeline.value))
const canRun = computed(() => perms.canRun.value)

async function loadRuns() {
  loading.value = true
  try {
    const [pipe, list] = await Promise.all([pipelineService.get(id), pipelineService.listRuns(id)])
    pipeline.value = pipe
    runs.value = list
  } finally {
    loading.value = false
  }
}

async function loadArtifacts(run: PipelineRun | null) {
  artifacts.value = []
  artifactsError.value = null
  if (!run) return
  artifactsLoading.value = true
  try {
    artifacts.value = await pipelineService.listArtifacts(id, run.id)
  } catch (error) {
    artifactsError.value = error instanceof ApiError ? error.message : 'Unable to load artifacts for this run.'
  } finally {
    artifactsLoading.value = false
  }
}

watch(selected, (run) => {
  void loadArtifacts(run)
})

async function retrySelected() {
  if (!selected.value || !canRun.value) return
  selected.value = await pipelineService.retryRun(id, selected.value.id)
  await loadRuns()
}
async function cancelSelected() {
  if (!selected.value || !canRun.value) return
  selected.value = await pipelineService.cancelRun(id, selected.value.id)
  await loadRuns()
}
async function downloadArtifact(artifact: PipelineArtifact) {
  if (!selected.value) return
  downloadingId.value = artifact.id
  try {
    const link = await pipelineService.createArtifactDownloadUrl(id, selected.value.id, artifact.id)
    window.open(link.url, '_blank', 'noopener')
  } finally {
    downloadingId.value = null
  }
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
        <VipButton variant="tertiary" icon="calendar" @click="router.push(`/pipelines/${id}/schedules`)"
          >Schedules</VipButton
        >
        <VipButton variant="tertiary" icon="chevronLeft" @click="router.push(`/pipelines/${id}`)"
          >Open in studio</VipButton
        >
      </template>
    </VipPageHeader>

    <p v-if="loading" aria-live="polite">Loading run history…</p>
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
        <p v-if="selected.errorMessage" class="rn-error">{{ selected.errorMessage }}</p>
        <div class="rn-actions">
          <VipButton
            v-if="selected.status === 'failed' && canRun"
            variant="secondary"
            size="sm"
            icon="refresh"
            title="Retry requires operator access"
            @click="retrySelected"
            >Retry run</VipButton
          >
          <VipButton
            v-if="['queued', 'running', 'waiting', 'retrying'].includes(selected.status) && canRun"
            variant="danger"
            size="sm"
            icon="close"
            title="Cancel requires operator access"
            @click="cancelSelected"
            >Cancel</VipButton
          >
          <VipButton variant="tertiary" size="sm" icon="copy" @click="copyDiagnostics">Copy diagnostics</VipButton>
        </div>
        <div class="rn-artifacts">
          <h4>Artifacts</h4>
          <p v-if="artifactsLoading">Loading artifacts…</p>
          <p v-else-if="artifactsError">{{ artifactsError }}</p>
          <p v-else-if="!artifacts.length">No artifacts for this run.</p>
          <ul v-else>
            <li v-for="art in artifacts" :key="art.id" class="rn-artifact">
              <div>
                <strong>{{ art.nodeKey }}</strong>
                <span>{{ art.contentType }} · {{ (art.sizeBytes / 1024).toFixed(1) }} KB</span>
                <span>Expires {{ new Date(art.expiresAt).toLocaleString() }}</span>
              </div>
              <VipButton
                variant="secondary"
                size="xs"
                icon="download"
                :loading="downloadingId === art.id"
                @click="downloadArtifact(art)"
                >Download</VipButton
              >
            </li>
          </ul>
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
  flex-wrap: wrap;
  margin: var(--vip-sp-5) 0;
}
.rn-error {
  margin-top: var(--vip-sp-4);
  color: var(--vip-danger);
  font-size: var(--vip-fs-sm);
}
.rn-artifacts {
  margin-top: var(--vip-sp-6);
}
.rn-artifacts h4 {
  margin: 0 0 var(--vip-sp-3);
  font-size: var(--vip-fs-sm);
}
.rn-artifact {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-3) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
  font-size: var(--vip-fs-sm);
}
.rn-artifact div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rn-artifact span {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-xs);
}
</style>
