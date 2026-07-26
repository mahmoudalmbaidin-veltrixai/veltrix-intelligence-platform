<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { pipelineService } from './pipelines.service'
import { usePlatformStore } from '@/shared/stores/platform'
import type { PipelineListItem } from '@/shared/types/pipeline'
import { relativeTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipConfirmDialog from '@/shared/ui/VipConfirmDialog.vue'
import { useUiStore } from '@/shared/stores/ui'
import { safeErrorText } from '@/shared/lib/safeError'

const router = useRouter()
const platform = usePlatformStore()
const ui = useUiStore()
const { data, isLoading, refetch } = useQuery('pipelines:list', () => pipelineService.list())

// --- Delete lifecycle (backend soft-archives; no restore, no separate archive) ---
const canDelete = computed(() => platform.can('pipeline.delete'))
const target = ref<PipelineListItem | null>(null)
const pending = ref(false)
const errorMsg = ref<string | null>(null)

function rowMenu() {
  return canDelete.value ? [{ key: 'delete', label: 'Delete', icon: 'trash', danger: true }] : []
}
function onRowMenu(row: PipelineListItem, key: string) {
  if (key === 'delete') {
    errorMsg.value = null
    target.value = row
  }
}
function closeDelete() {
  if (pending.value) return
  target.value = null
  errorMsg.value = null
}
async function confirmDelete() {
  if (!target.value) return
  pending.value = true
  errorMsg.value = null
  try {
    await pipelineService.remove(target.value.id, target.value.version)
    ui.pushToast({ kind: 'success', title: 'Pipeline deleted', message: target.value.name })
    target.value = null
    await refetch()
  } catch (e) {
    errorMsg.value = safeErrorText(e)
  } finally {
    pending.value = false
  }
}

const search = ref('')
const statusFilter = ref<'all' | 'published' | 'draft'>('all')
const sortKey = ref('')
const sortDir = ref<'asc' | 'desc'>('asc')

const rows = computed(() => {
  let items = data.value ?? []
  if (statusFilter.value !== 'all') items = items.filter((p) => p.status === statusFilter.value)
  const q = search.value.trim().toLowerCase()
  if (q) items = items.filter((p) => p.name.toLowerCase().includes(q) || p.tags.some((t) => t.includes(q)))
  if (sortKey.value === 'name') {
    items = [...items].sort((a, b) => a.name.localeCompare(b.name) * (sortDir.value === 'asc' ? 1 : -1))
  }
  return items
})

function onSort(key: string) {
  if (sortKey.value === key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

const columns = computed<Column<PipelineListItem>[]>(() => [
  { key: 'name', label: 'Pipeline', sortable: true },
  { key: 'status', label: 'Status' },
  { key: 'lastRun', label: 'Last run' },
  { key: 'nextSchedule', label: 'Next run' },
  { key: 'owner', label: 'Owner' },
  { key: 'version', label: 'Version', align: 'right' },
  ...(canDelete.value ? [{ key: 'actions', label: '', align: 'right' as const }] : []),
])

function statusTone(s?: string) {
  return s === 'succeeded' ? 'success' : s === 'failed' ? 'danger' : s === 'running' ? 'info' : 'neutral'
}
</script>

<template>
  <div>
    <VipPageHeader title="Pipelines" description="Design, validate, publish and monitor data pipelines.">
      <template #actions>
        <VipButton
          v-if="platform.can('pipeline.create')"
          variant="primary"
          icon="plus"
          @click="router.push('/pipelines/new')"
          >New pipeline</VipButton
        >
      </template>
    </VipPageHeader>

    <div class="pl-toolbar">
      <VipInput v-model="search" icon="search" placeholder="Search pipelines or tags…" size="sm" />
      <VipSegmented
        v-model="statusFilter"
        :options="[
          { value: 'all', label: 'All' },
          { value: 'published', label: 'Published' },
          { value: 'draft', label: 'Drafts' },
        ]"
        size="sm"
      />
    </div>

    <VipTable
      :columns="columns"
      :rows="rows"
      :row-key="(r) => r.id"
      :loading="isLoading"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      clickable
      empty-title="No pipelines"
      empty-description="Create your first pipeline to start moving data."
      @row-click="(r) => router.push(`/pipelines/${r.id}`)"
      @sort="onSort"
    >
      <template #cell-name="{ row }">
        <div class="pl-name">
          <VipIcon name="workflow" :size="15" />
          <div>
            <div class="pl-name__title">{{ row.name }}</div>
            <div class="pl-name__tags">
              <span v-for="t in row.tags" :key="t" class="pl-tag">{{ t }}</span>
              <span class="pl-nodes">{{ row.nodeCount }} nodes</span>
            </div>
          </div>
        </div>
      </template>
      <template #cell-status="{ row }">
        <VipBadge :tone="row.status === 'published' ? 'success' : 'neutral'" size="sm">{{ row.status }}</VipBadge>
      </template>
      <template #cell-lastRun="{ row }">
        <span v-if="row.lastRunAt" class="pl-run">
          <VipBadge :tone="statusTone(row.lastRunStatus)" variant="dot" size="sm">{{ row.lastRunStatus }}</VipBadge>
          <span class="pl-muted">{{ relativeTime(row.lastRunAt) }}</span>
        </span>
        <span v-else class="pl-muted">Never run</span>
      </template>
      <template #cell-nextSchedule="{ row }">
        <span class="pl-muted">{{ row.nextSchedule ? relativeTime(row.nextSchedule) : '—' }}</span>
      </template>
      <template #cell-version="{ row }"
        ><span class="pl-muted">v{{ row.version }}</span></template
      >
      <template #cell-actions="{ row }">
        <div class="pl-actions" @click.stop>
          <VipMenu :items="rowMenu()" align="end" @select="onRowMenu(row, $event)">
            <template #trigger>
              <button class="pl-menu" :aria-label="`Actions for ${row.name}`">
                <VipIcon name="dotsV" :size="16" />
              </button>
            </template>
          </VipMenu>
        </div>
      </template>
    </VipTable>

    <VipConfirmDialog
      :open="!!target"
      level="danger"
      title="Delete pipeline?"
      :resource-name="target?.name"
      message="Delete is an elevated, audited action that removes this pipeline from active lists."
      :impact="[
        'Future scheduled and manual runs will be blocked.',
        'Run history, versions and logs are retained server-side but no longer accessible here.',
        'Downstream datasets or dashboards that depend on it may be affected.',
      ]"
      note="The server soft-archives on delete; there is no in-app restore, so treat this as final."
      confirm-label="Delete"
      require-typing
      :pending="pending"
      :error="errorMsg"
      @confirm="confirmDelete"
      @cancel="closeDelete"
    />
  </div>
</template>

<style scoped>
.pl-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  margin-bottom: var(--vip-sp-6);
  flex-wrap: wrap;
}
.pl-name {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  color: var(--vip-text-muted);
}
.pl-name__title {
  color: var(--vip-text-primary);
  font-weight: var(--vip-fw-medium);
}
.pl-name__tags {
  display: flex;
  gap: var(--vip-sp-3);
  margin-top: 3px;
}
.pl-tag {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-brand-text);
  background: var(--vip-brand-soft);
  padding: 1px 6px;
  border-radius: var(--vip-radius-full);
}
.pl-nodes {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-disabled);
}
.pl-run {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
}
.pl-muted {
  color: var(--vip-text-muted);
}
.pl-actions {
  display: flex;
  justify-content: flex-end;
}
.pl-menu {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: var(--vip-text-secondary);
  background: none;
  border: 1px solid transparent;
  border-radius: var(--vip-radius-md);
}
.pl-menu:hover {
  background: var(--vip-surface-hover);
  border-color: var(--vip-border);
  color: var(--vip-text-primary);
}
</style>
