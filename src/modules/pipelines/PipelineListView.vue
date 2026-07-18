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

const router = useRouter()
const platform = usePlatformStore()
const { data, isLoading } = useQuery('pipelines:list', () => pipelineService.list())

const search = ref('')
const statusFilter = ref<'all' | 'published' | 'draft'>('all')

const rows = computed(() => {
  let items = data.value ?? []
  if (statusFilter.value !== 'all') items = items.filter((p) => p.status === statusFilter.value)
  const q = search.value.trim().toLowerCase()
  if (q) items = items.filter((p) => p.name.toLowerCase().includes(q) || p.tags.some((t) => t.includes(q)))
  return items
})

const columns: Column<PipelineListItem>[] = [
  { key: 'name', label: 'Pipeline', sortable: true },
  { key: 'status', label: 'Status' },
  { key: 'lastRun', label: 'Last run' },
  { key: 'nextSchedule', label: 'Next run' },
  { key: 'owner', label: 'Owner' },
  { key: 'version', label: 'Version', align: 'right' },
]

function statusTone(s?: string) {
  return s === 'succeeded' ? 'success' : s === 'failed' ? 'danger' : s === 'running' ? 'info' : 'neutral'
}
</script>

<template>
  <div>
    <VipPageHeader title="Pipelines" description="Design, validate, publish and monitor data pipelines.">
      <template #actions>
        <VipButton
          v-if="platform.can('pipeline:write')"
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
      clickable
      empty-title="No pipelines"
      empty-description="Create your first pipeline to start moving data."
      @row-click="(r) => router.push(`/pipelines/${r.id}`)"
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
    </VipTable>
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
</style>
