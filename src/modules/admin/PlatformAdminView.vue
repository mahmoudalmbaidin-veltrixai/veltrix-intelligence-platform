<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { adminService, type OrgRow } from './admin.service'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime, formatNumber } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const { data, isLoading } = useQuery('admin:orgs', () => adminService.listOrgs())
const filter = ref<'all' | 'active' | 'trial' | 'suspended'>('all')
const selected = ref<OrgRow | null>(null)

const rows = computed(() => (filter.value === 'all' ? data.value ?? [] : (data.value ?? []).filter((o) => o.status === filter.value)))
const columns: Column<OrgRow>[] = [
  { key: 'name', label: 'Organization' }, { key: 'status', label: 'Status' }, { key: 'plan', label: 'Plan' },
  { key: 'members', label: 'Members', align: 'right' }, { key: 'createdAt', label: 'Created' },
]
function tone(s: OrgRow['status']) {
  return s === 'active' ? 'success' : s === 'trial' ? 'info' : s === 'suspended' ? 'warning' : 'danger'
}
</script>

<template>
  <div>
    <VipPageHeader title="Platform Administration" description="Manage every tenant organization across the platform.">
      <template #actions>
        <VipSegmented v-model="filter" :options="[{ value: 'all', label: 'All' }, { value: 'active', label: 'Active' }, { value: 'trial', label: 'Trial' }, { value: 'suspended', label: 'Suspended' }]" size="sm" />
      </template>
    </VipPageHeader>
    <VipTable :columns="columns" :rows="rows" :row-key="(r) => r.id" :loading="isLoading" clickable @row-click="(r) => (selected = r)">
      <template #cell-status="{ row }"><VipBadge :tone="tone(row.status)" size="sm">{{ row.status }}</VipBadge></template>
      <template #cell-members="{ row }">{{ formatNumber(row.members) }}</template>
      <template #cell-createdAt="{ row }">{{ relativeTime(row.createdAt) }}</template>
    </VipTable>

    <VipDrawer :open="!!selected" :title="selected?.name" :width="440" @close="selected = null">
      <template v-if="selected">
        <div class="pa-facts">
          <div class="pa-fact"><span>Status</span><VipBadge :tone="tone(selected.status)" size="sm">{{ selected.status }}</VipBadge></div>
          <div class="pa-fact"><span>Plan</span>{{ selected.plan }}</div>
          <div class="pa-fact"><span>Members</span>{{ formatNumber(selected.members) }}</div>
          <div class="pa-fact"><span>Created</span>{{ relativeTime(selected.createdAt) }}</div>
        </div>
        <div class="pa-section">Support access</div>
        <VipButton variant="secondary" size="sm" icon="eye" block @click="ui.pushToast({ kind: 'info', title: 'Impersonation', message: 'Support impersonation is a governed backend capability (audited).' })">Request support access</VipButton>
        <div class="pa-section">Tenant lifecycle</div>
        <div class="pa-life">
          <VipButton variant="tertiary" size="sm" @click="ui.pushToast({ kind: 'info', title: 'Suspend tenant', message: 'Requires backend confirmation.' })">Suspend</VipButton>
          <VipButton variant="danger" size="sm" @click="ui.pushToast({ kind: 'warning', title: 'Schedule deletion', message: 'Pending-deletion workflow is backend-gated.' })">Schedule deletion</VipButton>
        </div>
      </template>
    </VipDrawer>
  </div>
</template>

<style scoped>
.pa-facts { display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.pa-fact { display: flex; align-items: center; justify-content: space-between; padding: var(--vip-sp-4) 0; border-bottom: 1px solid var(--vip-border-subtle); font-size: var(--vip-fs-sm); }
.pa-fact span { color: var(--vip-text-muted); }
.pa-section { font-size: var(--vip-fs-xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-muted); margin: var(--vip-sp-7) 0 var(--vip-sp-4); }
.pa-life { display: flex; gap: var(--vip-sp-3); }
</style>
