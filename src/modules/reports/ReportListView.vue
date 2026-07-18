<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { relativeTime } from '@/shared/lib/format'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import { reportService, type Report, type ReportStatus } from './reports.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const router = useRouter()
const ui = useUiStore()
const platform = usePlatformStore()
const canWrite = computed(() => platform.can('report:write'))

const { data: reports, isLoading } = useQuery(
  () => 'reports:list',
  () => reportService.list(),
)
const { data: templates, isLoading: templatesLoading } = useQuery(
  () => 'reports:templates',
  () => reportService.listTemplates(),
)

const tab = ref<'all' | 'templates'>('all')
const tabs = computed(() => [
  { value: 'all', label: 'All reports', count: reports.value?.length },
  { value: 'templates', label: 'Templates', count: templates.value?.length },
])

const STATUS_TONE: Record<ReportStatus, 'neutral' | 'warning' | 'info' | 'success' | 'danger'> = {
  draft: 'neutral',
  'in-review': 'warning',
  approved: 'info',
  published: 'success',
  rejected: 'danger',
}
const STATUS_LABEL: Record<ReportStatus, string> = {
  draft: 'Draft',
  'in-review': 'In review',
  approved: 'Approved',
  published: 'Published',
  rejected: 'Rejected',
}

const columns: Column<Report>[] = [
  { key: 'name', label: 'Report' },
  { key: 'status', label: 'Status' },
  { key: 'owner', label: 'Owner' },
  { key: 'version', label: 'Version', align: 'right' },
  { key: 'updatedAt', label: 'Updated', align: 'right' },
]

function openReport(r: Report) {
  router.push(`/reports/${r.id}`)
}
function newReport() {
  if (!canWrite.value) {
    ui.pushToast({
      kind: 'warning',
      title: 'Insufficient permission',
      message: 'You need report:write to create a report.',
    })
    return
  }
  router.push('/reports/new')
}
function useTemplate(name: string) {
  if (!canWrite.value) return
  ui.pushToast({ kind: 'info', title: 'Template selected', message: `Starting a new report from “${name}”.` })
  router.push('/reports/new')
}
</script>

<template>
  <div class="wrap">
    <VipPageHeader
      title="Reports"
      description="Author, review and publish governed reports, then schedule them for delivery."
    >
      <template #actions>
        <VipButton variant="secondary" icon="calendarClock" @click="router.push('/reports/deliveries')"
          >Deliveries</VipButton
        >
        <VipButton variant="primary" icon="plus" :disabled="!canWrite" @click="newReport">New report</VipButton>
      </template>
      <template #tabs>
        <VipTabs v-model="tab" :tabs="tabs" />
      </template>
    </VipPageHeader>

    <VipCard v-if="tab === 'all'" :padded="false">
      <VipTable
        :columns="columns"
        :rows="reports ?? []"
        :row-key="(r) => r.id"
        :loading="isLoading"
        clickable
        empty-title="No reports yet"
        empty-description="Create your first report to get started."
        @row-click="openReport"
      >
        <template #cell-name="{ row }">
          <div class="c-name">
            <span class="c-name__label">{{ row.name }}</span>
            <span class="c-name__desc">{{ row.description }}</span>
          </div>
        </template>
        <template #cell-status="{ row }">
          <VipBadge :tone="STATUS_TONE[row.status]" variant="soft" size="sm">{{ STATUS_LABEL[row.status] }}</VipBadge>
        </template>
        <template #cell-version="{ value }"
          ><span class="mono">{{ value }}</span></template
        >
        <template #cell-updatedAt="{ value }">{{ relativeTime(String(value)) }}</template>
      </VipTable>
    </VipCard>

    <div v-else class="tpl-grid">
      <template v-if="templatesLoading">
        <VipCard v-for="n in 6" :key="n">
          <VipSkeleton width="50%" height="15px" />
          <VipSkeleton width="90%" height="11px" style="margin-top: 10px" />
        </VipCard>
      </template>
      <VipCard v-for="t in templates" v-else :key="t.id" hoverable @click="useTemplate(t.name)">
        <div class="tpl__head">
          <span class="tpl__icon"><VipIcon name="report" :size="18" /></span>
          <h3 class="tpl__title">{{ t.name }}</h3>
        </div>
        <p class="tpl__desc">{{ t.description }}</p>
        <div class="tpl__foot">
          <VipBadge tone="neutral" variant="soft" size="sm">{{ t.sections }} sections</VipBadge>
          <span class="tpl__cta">Use template <VipIcon name="chevronRight" :size="13" /></span>
        </div>
      </VipCard>
    </div>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 1120px;
}
.c-name {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.c-name__label {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.c-name__desc {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  max-width: 380px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mono {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}

.tpl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--vip-sp-6);
}
.tpl__head {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.tpl__icon {
  width: 34px;
  height: 34px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
  border-radius: var(--vip-radius-md);
}
.tpl__title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
}
.tpl__desc {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  margin-top: var(--vip-sp-5);
  line-height: var(--vip-lh-normal);
}
.tpl__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--vip-sp-6);
}
.tpl__cta {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  color: var(--vip-brand-text);
  font-weight: var(--vip-fw-medium);
}
</style>
