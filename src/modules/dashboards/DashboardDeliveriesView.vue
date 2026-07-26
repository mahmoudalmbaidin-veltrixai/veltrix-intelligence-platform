<script setup lang="ts">
import { ref, watch } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { deliveryService, type ScheduledDelivery } from './delivery.service'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime, formatDateTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const { data, refetch } = useQuery('dashboard:deliveries', () => deliveryService.list())
const rows = ref<ScheduledDelivery[]>([])
watch(
  data,
  (d) => {
    if (d) rows.value = d
  },
  { immediate: true },
)

const columns: Column<ScheduledDelivery>[] = [
  { key: 'name', label: 'Delivery' },
  { key: 'subject', label: 'Subject' },
  { key: 'recipients', label: 'Recipients' },
  { key: 'format', label: 'Format' },
  { key: 'schedule_type', label: 'Cadence' },
  { key: 'next_run_at', label: 'Next run' },
  { key: 'enabled', label: 'Active', align: 'center' },
  { key: 'actions', label: '', align: 'right' },
]

async function toggle(d: ScheduledDelivery) {
  const updated = await deliveryService.toggle(d)
  Object.assign(d, updated)
  ui.pushToast({ kind: 'info', title: d.enabled ? 'Delivery resumed' : 'Delivery paused' })
}
async function remove(d: ScheduledDelivery) {
  await deliveryService.remove(d)
  refetch()
  ui.pushToast({ kind: 'info', title: 'Delivery removed', message: d.subject })
}
</script>

<template>
  <div>
    <VipPageHeader
      title="Scheduled Deliveries"
      description="Dashboards emailed to recipients on a schedule. Configure new deliveries from any dashboard's Share menu."
    />
    <VipTable
      :columns="columns"
      :rows="rows"
      :row-key="(r) => r.id"
      empty-title="No scheduled deliveries"
      empty-description="Open a dashboard and use Share → Email delivery to schedule one."
    >
      <template #cell-recipients="{ row }"
        ><span class="dd-muted">{{ row.recipients.length }} recipient(s)</span></template
      >
      <template #cell-format="{ row }"
        ><VipBadge tone="neutral" size="sm">{{ row.format.toUpperCase() }}</VipBadge></template
      >
      <template #cell-schedule_type="{ row }">{{ row.schedule_type.replace('_', ' ') }}</template>
      <template #cell-next_run_at="{ row }"
        ><span v-if="row.next_run_at" :title="formatDateTime(row.next_run_at)">{{ relativeTime(row.next_run_at) }}</span
        ><span v-else class="dd-muted">Not scheduled</span></template
      >
      <template #cell-enabled="{ row }"
        ><VipSwitch :model-value="row.enabled" size="sm" @update:model-value="toggle(row)"
      /></template>
      <template #cell-actions="{ row }"
        ><VipButton variant="ghost" size="xs" icon="trash" @click="remove(row)"
      /></template>
    </VipTable>
  </div>
</template>

<style scoped>
.dd-muted {
  color: var(--vip-text-muted);
}
</style>
