<script setup lang="ts">
import { ref } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { automationService, type AutomationRun } from './automation.service'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime, formatDuration } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const { data, isLoading } = useQuery('automation:runs', () => automationService.listRuns())
const selected = ref<AutomationRun | null>(null)

const columns: Column<AutomationRun>[] = [
  { key: 'automation', label: 'Automation' },
  { key: 'status', label: 'Status' },
  { key: 'startedAt', label: 'Started' },
  { key: 'durationMs', label: 'Duration' },
  { key: 'steps', label: 'Steps', align: 'right' },
]
function tone(s: AutomationRun['status']) {
  return s === 'succeeded' ? 'success' : s === 'failed' || s === 'dead-letter' ? 'danger' : s === 'running' ? 'info' : 'warning'
}
function stepTone(s: string) {
  return s === 'succeeded' ? 'success' : s === 'failed' ? 'danger' : s === 'running' ? 'info' : 'neutral'
}
function act(label: string) {
  ui.pushToast({ kind: 'info', title: label, message: 'Run control connects to the orchestration backend.' })
}
</script>

<template>
  <div>
    <VipPageHeader title="Automation runs" description="Execution history across all automations, including dead-letter failures." />
    <VipTable :columns="columns" :rows="data ?? []" :row-key="(r) => r.id" :loading="isLoading" clickable @row-click="(r) => (selected = r)">
      <template #cell-status="{ row }"><VipBadge :tone="tone(row.status)" size="sm">{{ row.status }}</VipBadge></template>
      <template #cell-startedAt="{ row }">{{ relativeTime(row.startedAt) }}</template>
      <template #cell-durationMs="{ row }">{{ formatDuration(row.durationMs) }}</template>
      <template #cell-steps="{ row }">{{ row.steps.length }}</template>
    </VipTable>

    <VipDrawer :open="!!selected" :title="selected?.automation" :width="460" @close="selected = null">
      <template v-if="selected">
        <div class="ar-status"><VipBadge :tone="tone(selected.status)">{{ selected.status }}</VipBadge><span>{{ relativeTime(selected.startedAt) }} · {{ formatDuration(selected.durationMs) }}</span></div>
        <div class="ar-section">Step trace</div>
        <ol class="ar-steps">
          <li v-for="(s, i) in selected.steps" :key="i" class="ar-step">
            <VipBadge :tone="stepTone(s.status)" variant="dot" size="sm" />
            <span class="ar-step-name">{{ s.name }}</span>
            <span class="ar-step-type">{{ s.type }}</span>
          </li>
        </ol>
        <div class="ar-actions">
          <VipButton v-if="selected.status === 'failed' || selected.status === 'dead-letter'" variant="secondary" size="sm" icon="refresh" @click="act('Retry run')">Retry</VipButton>
          <VipButton v-if="selected.status === 'running'" variant="danger" size="sm" icon="close" @click="act('Cancel run')">Cancel</VipButton>
          <VipButton v-if="selected.status === 'waiting-approval'" variant="primary" size="sm" icon="check" @click="act('Resume after approval')">Resume</VipButton>
          <VipButton variant="tertiary" size="sm" icon="copy" @click="act('Copy diagnostics')">Diagnostics</VipButton>
        </div>
        <div v-if="selected.status === 'dead-letter'" class="ar-dead"><VipIcon name="warning" :size="14" /> Moved to dead-letter after exhausting retries. Duplicate-action protection prevented re-execution of completed steps.</div>
      </template>
    </VipDrawer>
  </div>
</template>

<style scoped>
.ar-status { display: flex; align-items: center; gap: var(--vip-sp-4); font-size: var(--vip-fs-sm); color: var(--vip-text-muted); margin-bottom: var(--vip-sp-6); }
.ar-section { font-size: var(--vip-fs-xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-muted); margin-bottom: var(--vip-sp-4); }
.ar-steps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vip-sp-2); }
.ar-step { display: flex; align-items: center; gap: var(--vip-sp-3); padding: var(--vip-sp-3) var(--vip-sp-4); background: var(--vip-surface-2); border-radius: var(--vip-radius-sm); }
.ar-step-name { flex: 1; font-size: var(--vip-fs-sm); }
.ar-step-type { font-size: var(--vip-fs-2xs); color: var(--vip-text-disabled); font-family: var(--vip-font-mono); }
.ar-actions { display: flex; gap: var(--vip-sp-3); margin-top: var(--vip-sp-6); }
.ar-dead { display: flex; gap: var(--vip-sp-3); margin-top: var(--vip-sp-5); padding: var(--vip-sp-4); background: var(--vip-danger-soft); color: var(--vip-danger-text); border-radius: var(--vip-radius-md); font-size: var(--vip-fs-xs); }
</style>
