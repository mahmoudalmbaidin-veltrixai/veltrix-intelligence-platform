<script setup lang="ts">
import { ref } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime, formatDuration, formatNumber } from '@/shared/lib/format'
import { aiService, type AgentRun, type AgentRunStatus, type AgentRunStep } from './ai.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const { data, isLoading } = useQuery('ai:agent-runs', () => aiService.listAgentRuns())

const STATUS_TONE: Record<AgentRunStatus, 'success' | 'info' | 'danger' | 'neutral'> = {
  succeeded: 'success',
  running: 'info',
  failed: 'danger',
  queued: 'neutral',
}
const STEP_ICON: Record<AgentRunStep['status'], string> = {
  succeeded: 'check',
  running: 'refresh',
  failed: 'error',
  queued: 'clock',
}
const STEP_TONE: Record<AgentRunStep['status'], 'success' | 'info' | 'danger' | 'neutral'> = {
  succeeded: 'success',
  running: 'info',
  failed: 'danger',
  queued: 'neutral',
}

const columns: Column<AgentRun>[] = [
  { key: 'agent', label: 'Agent', width: '28%' },
  { key: 'status', label: 'Status' },
  { key: 'startedAt', label: 'Started' },
  { key: 'durationMs', label: 'Duration', align: 'right' },
  { key: 'tokens', label: 'Tokens', align: 'right' },
  { key: 'cost', label: 'Cost', align: 'right' },
]

const selected = ref<AgentRun | null>(null)
function openRun(run: AgentRun): void {
  selected.value = run
}

function cancelRun(): void {
  if (!selected.value) return
  ui.pushToast({
    kind: 'warning',
    title: 'Cancellation requested',
    message: `Run ${selected.value.id} will stop after the current step.`,
  })
}
function retryRun(): void {
  if (!selected.value) return
  ui.pushToast({ kind: 'info', title: 'Retry queued', message: `A new run of “${selected.value.agent}” was queued.` })
}
</script>

<template>
  <div class="runs">
    <VipPageHeader title="Agent runs" description="Execution history and step traces for your autonomous agents." />

    <VipCard :padded="false">
      <VipTable
        :columns="columns"
        :rows="data ?? []"
        :row-key="(r) => r.id"
        :loading="isLoading"
        clickable
        density="compact"
        empty-title="No runs yet"
        empty-description="Agent runs will appear here once your agents execute."
        @row-click="openRun"
      >
        <template #cell-agent="{ row }">
          <div class="runs__agent">
            <VipIcon name="bot" :size="14" class="runs__agent-icon" />
            <span class="runs__agent-name">{{ row.agent }}</span>
          </div>
        </template>
        <template #cell-status="{ row }">
          <VipBadge :tone="STATUS_TONE[row.status]" variant="soft" size="sm">
            <span v-if="row.status === 'running'" class="runs__pulse" />{{ row.status }}
          </VipBadge>
        </template>
        <template #cell-startedAt="{ row }">
          <span class="runs__muted">{{ relativeTime(row.startedAt) }}</span>
        </template>
        <template #cell-durationMs="{ row }">
          <span class="runs__mono">{{ formatDuration(row.durationMs) }}</span>
        </template>
        <template #cell-tokens="{ row }">
          <span class="runs__mono">{{ row.tokens != null ? formatNumber(row.tokens) : '—' }}</span>
        </template>
        <template #cell-cost="{ row }">
          <span class="runs__mono">{{ row.cost != null ? `$${row.cost.toFixed(2)}` : '—' }}</span>
        </template>
      </VipTable>
    </VipCard>

    <!-- Run detail drawer -->
    <VipDrawer :open="!!selected" :title="selected?.agent" :width="560" @close="selected = null">
      <div v-if="selected" class="runs__detail">
        <div class="runs__head">
          <VipBadge :tone="STATUS_TONE[selected.status]" variant="soft">{{ selected.status }}</VipBadge>
          <span class="runs__id">{{ selected.id }}</span>
        </div>

        <div class="runs__stats">
          <div class="runs__stat">
            <span class="runs__stat-v">{{ formatDuration(selected.durationMs) }}</span
            ><span class="runs__stat-l">Duration</span>
          </div>
          <div class="runs__stat">
            <span class="runs__stat-v">{{ selected.tokens != null ? formatNumber(selected.tokens) : '—' }}</span
            ><span class="runs__stat-l">Tokens</span>
          </div>
          <div class="runs__stat">
            <span class="runs__stat-v">{{ selected.cost != null ? `$${selected.cost.toFixed(2)}` : '—' }}</span
            ><span class="runs__stat-l">Cost</span>
          </div>
        </div>

        <section class="runs__section">
          <h4 class="runs__section-title">Step trace</h4>
          <ol class="runs__steps">
            <li v-for="(s, i) in selected.steps" :key="i" class="runs__step" :class="`is-${s.status}`">
              <span class="runs__step-dot"><VipIcon :name="STEP_ICON[s.status]" :size="12" /></span>
              <div class="runs__step-body">
                <span class="runs__step-name">{{ s.name }}</span>
                <span v-if="s.tool" class="runs__step-tool">{{ s.tool }}</span>
              </div>
              <VipBadge :tone="STEP_TONE[s.status]" variant="soft" size="sm">{{ s.status }}</VipBadge>
            </li>
          </ol>
        </section>

        <section class="runs__section">
          <h4 class="runs__section-title">Logs</h4>
          <pre class="runs__logs">
[00:00] Run accepted for agent "{{ selected.agent }}"
[00:01] Planning steps ({{ selected.steps.length }})
[00:02] Executing step 1 — {{ selected.steps[0]?.name }}
[00:14] {{ selected.status === 'failed' ? 'ERROR: tool call returned non-zero status' : 'Progressing normally' }}
[00:18] {{
              selected.status === 'succeeded'
                ? 'Run completed'
                : selected.status === 'running'
                  ? 'In progress…'
                  : 'Awaiting scheduler'
            }}</pre>
          <p class="runs__logs-note">Logs are redacted of prompt content and credentials.</p>
        </section>
      </div>
      <template #footer>
        <VipButton
          v-if="selected?.status === 'running' || selected?.status === 'queued'"
          variant="danger"
          icon="close"
          @click="cancelRun"
        >
          Cancel
        </VipButton>
        <VipButton v-if="selected?.status === 'failed'" variant="secondary" icon="refresh" @click="retryRun"
          >Retry</VipButton
        >
        <VipButton variant="secondary" @click="selected = null">Close</VipButton>
      </template>
    </VipDrawer>
  </div>
</template>

<style scoped>
.runs {
  max-width: 1280px;
  margin: 0 auto;
}
.runs__agent {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.runs__agent-icon {
  color: var(--vip-text-muted);
}
.runs__agent-name {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.runs__muted {
  color: var(--vip-text-muted);
}
.runs__mono {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}
.runs__pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: runs-pulse 1s ease-in-out infinite;
}
@keyframes runs-pulse {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}

.runs__detail {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-7);
}
.runs__head {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-5);
}
.runs__id {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.runs__stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--vip-sp-5);
}
.runs__stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--vip-sp-5);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
}
.runs__stat-v {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
  font-family: var(--vip-font-mono);
}
.runs__stat-l {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-muted);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
}

.runs__section {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.runs__section-title {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-semibold);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
}
.runs__steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.runs__step {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-4) var(--vip-sp-5);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
}
.runs__step-dot {
  width: 24px;
  height: 24px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--vip-surface-3);
  color: var(--vip-text-muted);
}
.runs__step.is-succeeded .runs__step-dot {
  background: var(--vip-success-soft);
  color: var(--vip-success-text);
}
.runs__step.is-running .runs__step-dot {
  background: var(--vip-info-soft);
  color: var(--vip-info-text);
}
.runs__step.is-failed .runs__step-dot {
  background: var(--vip-danger-soft);
  color: var(--vip-danger-text);
}
.runs__step-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.runs__step-name {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-primary);
}
.runs__step-tool {
  font-size: var(--vip-fs-2xs);
  font-family: var(--vip-font-mono);
  color: var(--vip-text-muted);
}
.runs__logs {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-secondary);
  background: var(--vip-surface-inset);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  padding: var(--vip-sp-5);
  overflow-x: auto;
  white-space: pre-wrap;
  line-height: var(--vip-lh-snug);
}
.runs__logs-note {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-muted);
}
</style>
