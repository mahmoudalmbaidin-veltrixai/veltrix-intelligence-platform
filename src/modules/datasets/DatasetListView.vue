<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { relativeTime, formatNumber } from '@/shared/lib/format'
import { datasetService, type Dataset, type DatasetStatus } from './datasets.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipCheckbox from '@/shared/ui/VipCheckbox.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTooltip from '@/shared/ui/VipTooltip.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const router = useRouter()

const { data, isLoading } = useQuery('datasets:list', () => datasetService.list())

const search = ref('')
const statusFilter = ref<'all' | DatasetStatus>('all')
const certifiedOnly = ref(false)

const statusOptions: { value: string; label: string }[] = [
  { value: 'all', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'building', label: 'Building' },
  { value: 'deprecated', label: 'Deprecated' },
]

const rows = computed<Dataset[]>(() => {
  const q = search.value.trim().toLowerCase()
  return (data.value ?? []).filter((d) => {
    const matchesSearch =
      !q ||
      d.name.toLowerCase().includes(q) ||
      d.description.toLowerCase().includes(q) ||
      d.owner.toLowerCase().includes(q) ||
      d.tags.some((t) => t.toLowerCase().includes(q))
    const matchesStatus = statusFilter.value === 'all' || d.status === statusFilter.value
    const matchesCertified = !certifiedOnly.value || d.certified
    return matchesSearch && matchesStatus && matchesCertified
  })
})

const STATUS_TONE: Record<DatasetStatus, 'success' | 'info' | 'neutral'> = {
  active: 'success',
  building: 'info',
  deprecated: 'neutral',
}

function qualityTone(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 90) return 'success'
  if (score >= 75) return 'warning'
  return 'danger'
}

const columns: Column<Dataset>[] = [
  { key: 'name', label: 'Dataset', width: '32%' },
  { key: 'owner', label: 'Owner' },
  { key: 'rowCount', label: 'Rows', align: 'right' },
  { key: 'qualityScore', label: 'Quality', align: 'right' },
  { key: 'freshness', label: 'Freshness', align: 'right' },
  { key: 'status', label: 'Status' },
]

function open(row: Dataset) {
  router.push(`/datasets/${row.id}`)
}
</script>

<template>
  <div class="dl">
    <VipPageHeader
      title="Datasets"
      description="Browse the certified and in-progress datasets across your workspaces."
    />

    <VipCard :padded="false">
      <div class="dl__toolbar">
        <div class="dl__search">
          <VipInput v-model="search" icon="search" size="sm" placeholder="Search datasets, owners or tags" />
        </div>
        <div class="dl__filters">
          <VipSelect v-model="statusFilter" :options="statusOptions" size="sm" />
          <VipCheckbox v-model="certifiedOnly" label="Certified only" />
          <span class="dl__count">{{ rows.length }} of {{ data?.length ?? 0 }}</span>
        </div>
      </div>

      <VipTable
        :columns="columns"
        :rows="rows"
        :row-key="(r) => r.id"
        :loading="isLoading"
        clickable
        empty-title="No datasets match"
        empty-description="Adjust your filters or search to see more results."
        @row-click="open"
      >
        <template #cell-name="{ row }">
          <div class="dl__name">
            <span class="dl__icon"><VipIcon name="database" :size="16" /></span>
            <div class="dl__name-text">
              <span class="dl__title">
                {{ row.name }}
                <VipTooltip v-if="row.certified" text="Certified dataset">
                  <VipIcon name="shield" :size="13" class="dl__certified" />
                </VipTooltip>
                <VipTooltip v-if="row.sensitive" text="Contains sensitive / PII data">
                  <VipIcon name="lock" :size="13" class="dl__sensitive" />
                </VipTooltip>
              </span>
              <span class="dl__desc">{{ row.description }}</span>
            </div>
          </div>
        </template>

        <template #cell-rowCount="{ row }">
          <span class="dl__num">{{ formatNumber(row.rowCount, { style: 'compact' }) }}</span>
        </template>

        <template #cell-qualityScore="{ row }">
          <VipBadge :tone="qualityTone(row.qualityScore)" variant="soft" size="sm">{{ row.qualityScore }}</VipBadge>
        </template>

        <template #cell-freshness="{ row }">
          <span class="dl__muted">{{ relativeTime(row.freshness) }}</span>
        </template>

        <template #cell-status="{ row }">
          <VipBadge :tone="STATUS_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge>
        </template>
      </VipTable>
    </VipCard>
  </div>
</template>

<style scoped>
.dl {
  max-width: 1280px;
  margin: 0 auto;
}
.dl__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-5) var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border-subtle);
  flex-wrap: wrap;
}
.dl__search {
  width: min(340px, 100%);
}
.dl__filters {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-6);
}
.dl__count {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  white-space: nowrap;
}
.dl__name {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-5);
}
.dl__icon {
  width: 32px;
  height: 32px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-3);
  color: var(--vip-text-secondary);
}
.dl__name-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.dl__title {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.dl__certified {
  color: var(--vip-success-text);
}
.dl__sensitive {
  color: var(--vip-warning-text);
}
.dl__desc {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 380px;
}
.dl__num {
  font-variant-numeric: tabular-nums;
}
.dl__muted {
  color: var(--vip-text-muted);
}
</style>
