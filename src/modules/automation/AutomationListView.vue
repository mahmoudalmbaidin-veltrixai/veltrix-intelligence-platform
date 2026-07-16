<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { relativeTime } from '@/shared/lib/format'
import {
  automationService,
  TRIGGER_META,
  type Automation,
  type AutomationStatus,
} from './automation.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const router = useRouter()
const { data, isLoading } = useQuery('automation:list', () => automationService.list())

const search = ref('')
const rows = computed<Automation[]>(() => {
  const all = data.value ?? []
  const q = search.value.trim().toLowerCase()
  if (!q) return all
  return all.filter(
    (a) =>
      a.name.toLowerCase().includes(q) ||
      a.owner.toLowerCase().includes(q) ||
      TRIGGER_META[a.trigger].label.toLowerCase().includes(q),
  )
})

const STATUS_TONE: Record<AutomationStatus, 'success' | 'warning' | 'neutral'> = {
  active: 'success',
  paused: 'warning',
  draft: 'neutral',
}

const columns: Column<Automation>[] = [
  { key: 'name', label: 'Automation', width: '34%' },
  { key: 'trigger', label: 'Trigger' },
  { key: 'status', label: 'Status' },
  { key: 'owner', label: 'Owner' },
  { key: 'lastRun', label: 'Last run', align: 'right' },
  { key: 'runsToday', label: 'Runs today', align: 'right' },
]

const templates = [
  { id: 'tpl_1', name: 'Failure alerting', desc: 'Notify on-call when a critical pipeline fails.', icon: 'bell' },
  { id: 'tpl_2', name: 'Scheduled briefing', desc: 'Email a KPI digest every morning.', icon: 'calendarClock' },
  { id: 'tpl_3', name: 'Quality quarantine', desc: 'Isolate a dataset when an incident is raised.', icon: 'gauge' },
  { id: 'tpl_4', name: 'Approval to publish', desc: 'Gate report publishing behind a human approval.', icon: 'check' },
]

function open(row: Automation): void {
  router.push(`/automation/${row.id}`)
}
</script>

<template>
  <div class="al">
    <VipPageHeader title="Automation" description="Event-driven workflows that react to pipelines, data quality and approvals.">
      <template #actions>
        <VipButton variant="primary" icon="plus" @click="router.push('/automation/new')">New automation</VipButton>
      </template>
    </VipPageHeader>

    <VipCard :padded="false">
      <div class="al__toolbar">
        <div class="al__search">
          <VipInput v-model="search" icon="search" size="sm" placeholder="Search by name, trigger or owner" />
        </div>
        <span class="al__count">{{ rows.length }} {{ rows.length === 1 ? 'automation' : 'automations' }}</span>
      </div>

      <VipTable
        :columns="columns"
        :rows="rows"
        :row-key="(r) => r.id"
        :loading="isLoading"
        clickable
        empty-title="No automations found"
        empty-description="Create an automation or start from a template below."
        @row-click="open"
      >
        <template #cell-name="{ row }">
          <div class="al__name">
            <span class="al__name-icon"><VipIcon name="workflow" :size="15" /></span>
            <span class="al__name-title">{{ row.name }}</span>
          </div>
        </template>
        <template #cell-trigger="{ row }">
          <span class="al__trigger">
            <VipIcon :name="TRIGGER_META[row.trigger].icon" :size="14" />
            {{ TRIGGER_META[row.trigger].label }}
          </span>
        </template>
        <template #cell-status="{ row }">
          <VipBadge :tone="STATUS_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge>
        </template>
        <template #cell-owner="{ row }">
          <span class="al__muted">{{ row.owner }}</span>
        </template>
        <template #cell-lastRun="{ row }">
          <span class="al__muted">{{ relativeTime(row.lastRun) }}</span>
        </template>
        <template #cell-runsToday="{ row }">
          <span class="al__mono">{{ row.runsToday }}</span>
        </template>
      </VipTable>
    </VipCard>

    <section class="al__templates">
      <h2 class="al__templates-title">Start from a template</h2>
      <div class="al__template-grid">
        <VipCard v-for="t in templates" :key="t.id" hoverable @click="router.push('/automation/new')">
          <div class="al__template-head"><span class="al__name-icon"><VipIcon :name="t.icon" :size="15" /></span></div>
          <h3 class="al__template-name">{{ t.name }}</h3>
          <p class="al__template-desc">{{ t.desc }}</p>
        </VipCard>
      </div>
    </section>
  </div>
</template>

<style scoped>
.al { max-width: 1280px; margin: 0 auto; }
.al__toolbar { display: flex; align-items: center; justify-content: space-between; gap: var(--vip-sp-5); padding: var(--vip-sp-5) var(--vip-sp-6); border-bottom: 1px solid var(--vip-border-subtle); }
.al__search { width: min(360px, 100%); }
.al__count { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); white-space: nowrap; }
.al__name { display: flex; align-items: center; gap: var(--vip-sp-5); }
.al__name-icon { width: 30px; height: 30px; flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: var(--vip-radius-md); background: var(--vip-surface-3); color: var(--vip-text-secondary); }
.al__name-title { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); }
.al__trigger { display: inline-flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }
.al__muted { color: var(--vip-text-muted); }
.al__mono { font-family: var(--vip-font-mono); font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }

.al__templates { margin-top: var(--vip-sp-9); }
.al__templates-title { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); margin-bottom: var(--vip-sp-5); }
.al__template-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--vip-sp-6); }
.al__template-head { margin-bottom: var(--vip-sp-5); }
.al__template-name { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); margin-bottom: var(--vip-sp-2); }
.al__template-desc { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }
</style>
