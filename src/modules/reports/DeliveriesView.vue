<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useQuery, useMutation } from '@/shared/lib/query'
import { relativeTime, formatDateTime } from '@/shared/lib/format'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import { isoAhead } from '@/shared/lib/mock'
import {
  reportService,
  type Delivery,
  type DeliverySchedule,
  type DeliveryFormat,
  type DeliveryStatus,
  type ExportJob,
  type ExportStatus,
} from './reports.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const platform = usePlatformStore()
const canWrite = computed(() => platform.can('report.schedule'))

const {
  data: deliveries,
  isLoading,
  refetch,
} = useQuery(
  () => 'reports:deliveries',
  () => reportService.listDeliveries(),
)
const { data: exports, isLoading: exportsLoading } = useQuery(
  () => 'reports:exports',
  () => reportService.listExports(),
)
const { data: reports } = useQuery(
  () => 'reports:list',
  () => reportService.list(),
)

const DELIVERY_STATUS_TONE: Record<DeliveryStatus, 'success' | 'danger' | 'warning'> = {
  sent: 'success',
  failed: 'danger',
  pending: 'warning',
}
const EXPORT_STATUS_TONE: Record<ExportStatus, 'info' | 'warning' | 'success' | 'neutral'> = {
  queued: 'info',
  rendering: 'warning',
  ready: 'success',
  expired: 'neutral',
}

const deliveryColumns: Column<Delivery>[] = [
  { key: 'report', label: 'Report' },
  { key: 'schedule', label: 'Schedule' },
  { key: 'format', label: 'Format' },
  { key: 'recipients', label: 'Recipients', align: 'right' },
  { key: 'nextRun', label: 'Next run', align: 'right' },
  { key: 'lastStatus', label: 'Last status' },
]
const exportColumns: Column<ExportJob>[] = [
  { key: 'report', label: 'Report' },
  { key: 'format', label: 'Format' },
  { key: 'status', label: 'Status' },
  { key: 'createdAt', label: 'Created', align: 'right' },
  { key: 'actions', label: '', align: 'right', width: '120px' },
]

const scheduleOptions = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
]
const formatOptions = [
  { value: 'pdf', label: 'PDF' },
  { value: 'excel', label: 'Excel' },
  { value: 'csv', label: 'CSV' },
]
const reportOptions = computed(() => (reports.value ?? []).map((r) => ({ value: r.name, label: r.name })))

/* ---- create delivery ---- */
const dialogOpen = ref(false)
interface Draft {
  report: string
  schedule: DeliverySchedule
  format: DeliveryFormat
  recipients: number
}
const draft = reactive<Draft>({ report: '', schedule: 'weekly', format: 'pdf', recipients: 1 })

function openDialog() {
  draft.report = reportOptions.value[0]?.value ?? ''
  draft.schedule = 'weekly'
  draft.format = 'pdf'
  draft.recipients = 1
  dialogOpen.value = true
}

const nextRunFor = (schedule: DeliverySchedule): string =>
  isoAhead(schedule === 'daily' ? 60 * 24 : schedule === 'weekly' ? 60 * 24 * 7 : 60 * 24 * 30)

const canSubmit = computed(() => !!draft.report && draft.recipients > 0)

const { mutate, isPending } = useMutation((input: Omit<Delivery, 'id'>) => reportService.createDelivery(input), {
  invalidate: ['reports:deliveries'],
  onSuccess: (d) => {
    ui.pushToast({
      kind: 'success',
      title: 'Delivery scheduled',
      message: `${d.report} · ${d.schedule} · ${d.format.toUpperCase()}`,
    })
    dialogOpen.value = false
    refetch()
  },
})

async function submit() {
  if (!canSubmit.value) return
  await mutate({
    report: draft.report,
    schedule: draft.schedule,
    format: draft.format,
    recipients: draft.recipients,
    nextRun: nextRunFor(draft.schedule),
    lastStatus: 'pending',
  })
}

function download(job: ExportJob) {
  if (job.status !== 'ready') {
    ui.pushToast({ kind: 'warning', title: 'Not available', message: `“${job.report}” is ${job.status}.` })
    return
  }
  ui.pushToast({ kind: 'success', title: 'Download started', message: `${job.report}.${job.format}` })
}
</script>

<template>
  <div class="wrap">
    <VipPageHeader
      title="Scheduled deliveries"
      description="Automated report distribution and recent on-demand exports."
    >
      <template #actions>
        <VipButton variant="primary" icon="plus" :disabled="!canWrite" @click="openDialog">New delivery</VipButton>
      </template>
    </VipPageHeader>

    <VipCard :padded="false">
      <VipTable
        :columns="deliveryColumns"
        :rows="deliveries ?? []"
        :row-key="(r) => r.id"
        :loading="isLoading"
        empty-title="No scheduled deliveries"
        empty-description="Schedule a report to have it delivered automatically."
      >
        <template #cell-report="{ value }"
          ><span class="strong">{{ value }}</span></template
        >
        <template #cell-schedule="{ value }"
          ><span class="cap">{{ value }}</span></template
        >
        <template #cell-format="{ value }"
          ><VipBadge tone="neutral" variant="soft" size="sm">{{ String(value).toUpperCase() }}</VipBadge></template
        >
        <template #cell-recipients="{ value }">
          <span class="recips"><VipIcon name="users" :size="13" /> {{ value }}</span>
        </template>
        <template #cell-nextRun="{ value }">{{ relativeTime(String(value)) }}</template>
        <template #cell-lastStatus="{ row }">
          <VipBadge :tone="DELIVERY_STATUS_TONE[row.lastStatus]" variant="soft" size="sm">{{
            row.lastStatus
          }}</VipBadge>
        </template>
      </VipTable>
    </VipCard>

    <section class="exports">
      <div class="exports__head">
        <h2 class="exports__title">Export history</h2>
        <span class="exports__sub">On-demand renders from the last 7 days</span>
      </div>
      <VipCard :padded="false">
        <VipTable
          :columns="exportColumns"
          :rows="exports ?? []"
          :row-key="(r) => r.id"
          :loading="exportsLoading"
          density="compact"
          empty-title="No exports yet"
        >
          <template #cell-report="{ value }"
            ><span class="strong">{{ value }}</span></template
          >
          <template #cell-format="{ value }"
            ><VipBadge tone="neutral" variant="soft" size="sm">{{ String(value).toUpperCase() }}</VipBadge></template
          >
          <template #cell-status="{ row }">
            <VipBadge :tone="EXPORT_STATUS_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge>
          </template>
          <template #cell-createdAt="{ value }">{{ formatDateTime(String(value)) }}</template>
          <template #cell-actions="{ row }">
            <VipButton
              variant="tertiary"
              size="xs"
              icon="download"
              :disabled="row.status !== 'ready'"
              @click="download(row)"
              >Download</VipButton
            >
          </template>
        </VipTable>
      </VipCard>
    </section>

    <VipDialog
      :open="dialogOpen"
      title="New delivery"
      description="Schedule automated distribution of a report."
      @close="dialogOpen = false"
    >
      <div class="form">
        <VipSelect v-model="draft.report" :options="reportOptions" label="Report" placeholder="Select a report" />
        <div class="row2">
          <VipSelect v-model="draft.schedule" :options="scheduleOptions" label="Schedule" />
          <VipSelect v-model="draft.format" :options="formatOptions" label="Format" />
        </div>
        <VipInput
          v-model.number="draft.recipients"
          type="number"
          label="Recipients"
          help="Number of subscribers on the distribution list."
        />
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="dialogOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="isPending" :disabled="!canSubmit" @click="submit"
          >Schedule delivery</VipButton
        >
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 1120px;
}
.strong {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.cap {
  text-transform: capitalize;
}
.recips {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
}

.exports {
  margin-top: var(--vip-sp-9);
}
.exports__head {
  display: flex;
  align-items: baseline;
  gap: var(--vip-sp-5);
  margin-bottom: var(--vip-sp-5);
}
.exports__title {
  font-size: var(--vip-fs-xl);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
}
.exports__sub {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-5);
}
</style>
