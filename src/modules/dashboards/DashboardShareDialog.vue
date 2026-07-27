<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { Dashboard } from '@/shared/types/dashboard'
import { relativeTime } from '@/shared/lib/format'
import { safeErrorText } from '@/shared/lib/safeError'
import { useUiStore } from '@/shared/stores/ui'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import {
  dashboardService,
  type DashboardShare,
  type DashboardSnapshot,
  type DashboardVersion,
} from './dashboards.service'
import {
  deliveryService,
  type DashboardExport,
  type DeliveryCadence,
  type DeliveryFormat,
  type DeliveryRun,
  type EmailPreview,
  type ExportFormat,
  type ScheduledDelivery,
} from './delivery.service'

const props = defineProps<{
  open: boolean
  dashboard: Dashboard
  initialTab?: 'export' | 'snapshot' | 'email'
}>()
const emit = defineEmits<{ close: []; updated: [dashboard: Dashboard] }>()
const ui = useUiStore()
const tab = ref<'versions' | 'sharing' | 'snapshot' | 'export' | 'delivery'>('versions')
const loading = ref(false)
const versions = ref<DashboardVersion[]>([])
const shares = ref<DashboardShare[]>([])
const snapshots = ref<DashboardSnapshot[]>([])
const exports = ref<DashboardExport[]>([])
const deliveries = ref<ScheduledDelivery[]>([])
const rowVersion = ref(1)
const principalId = ref('')
const snapLabel = ref('')
const exportFormat = ref<ExportFormat>('pdf')
// Exports and deliveries render the immutable published version, so they are only
// available once the dashboard has been published at least once.
const canExport = computed(() => props.dashboard.status === 'published')
const recipients = ref('')
const ccRecipients = ref('')
const bccRecipients = ref('')
const deliveryName = ref('Weekly dashboard')
const deliverySubject = ref('Dashboard delivery')
const deliveryFormat = ref<DeliveryFormat>('pdf')
const deliveryCadence = ref<DeliveryCadence>('weekly')
const deliveryCron = ref('0 8 * * 1')
const runAt = ref('')
const emailPreview = ref<EmailPreview | null>(null)
const deliveryRuns = ref<Record<string, DeliveryRun[]>>({})
let pollTimer: ReturnType<typeof setInterval> | undefined

function selectedTab(): typeof tab.value {
  if (props.initialTab === 'snapshot') return 'snapshot'
  if (props.initialTab === 'email') return 'delivery'
  if (props.initialTab === 'export') return 'export'
  return 'versions'
}

function parseAddresses(value: string): string[] {
  return value
    .split(/[;,\n]/)
    .map((value) => value.trim())
    .filter(Boolean)
}

async function refresh() {
  loading.value = true
  try {
    rowVersion.value = await dashboardService.rowVersion(props.dashboard.id)
    ;[versions.value, shares.value, snapshots.value, exports.value, deliveries.value] = await Promise.all([
      dashboardService.versions(props.dashboard.id),
      dashboardService.shares(props.dashboard.id),
      dashboardService.snapshots(props.dashboard.id),
      deliveryService.exports(props.dashboard.id),
      deliveryService.list(props.dashboard.id),
    ])
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Dashboard governance could not be loaded', message: safeErrorText(error) })
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!props.open || !exports.value.some((job) => ['queued', 'rendering'].includes(job.status))) return
    try {
      exports.value = await deliveryService.exports(props.dashboard.id)
    } catch {
      stopPolling()
      ui.pushToast({ kind: 'error', title: 'Export status could not be refreshed' })
    }
  }, 1500)
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = undefined
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      tab.value = selectedTab()
      void refresh().then(startPolling)
    } else stopPolling()
  },
)
onBeforeUnmount(stopPolling)

async function restore(version: DashboardVersion) {
  const restored = await dashboardService.restore(props.dashboard.id, version.id, rowVersion.value)
  rowVersion.value = restored.version
  emit('updated', restored)
  await refresh()
  ui.pushToast({ kind: 'success', title: `Version ${version.version_number} restored as a new draft` })
}

async function addShare() {
  const value = principalId.value.trim()
  if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value)) {
    ui.pushToast({ kind: 'error', title: 'Enter a valid workspace user UUID' })
    return
  }
  await dashboardService.createShare(props.dashboard.id, rowVersion.value, 'user', value, 'view')
  principalId.value = ''
  await refresh()
  ui.pushToast({ kind: 'success', title: 'Viewer access granted' })
}

async function revoke(share: DashboardShare) {
  await dashboardService.revokeShare(props.dashboard.id, share.id, rowVersion.value)
  await refresh()
  ui.pushToast({ kind: 'info', title: 'Share revoked' })
}

async function saveSnapshot() {
  const created = await dashboardService.createSnapshot(
    props.dashboard.id,
    snapLabel.value.trim() || `Snapshot ${new Date().toLocaleDateString()}`,
  )
  snapLabel.value = ''
  await refresh()
  ui.pushToast({ kind: 'success', title: 'Snapshot saved', message: created.name })
}

async function startExport() {
  try {
    const job = await deliveryService.createExport(props.dashboard.id, exportFormat.value)
    exports.value = [job, ...exports.value]
    startPolling()
    ui.pushToast({ kind: 'success', title: `${exportFormat.value.toUpperCase()} export queued` })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Export could not be queued', message: safeErrorText(error) })
  }
}

async function cancelExport(job: DashboardExport) {
  try {
    Object.assign(job, await deliveryService.cancelExport(job))
    ui.pushToast({ kind: 'info', title: 'Export cancellation requested' })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Export could not be cancelled', message: safeErrorText(error) })
  }
}

async function retryExport(job: DashboardExport) {
  try {
    Object.assign(job, await deliveryService.retryExport(job))
    startPolling()
    ui.pushToast({ kind: 'success', title: 'Export queued for retry' })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Export could not be retried', message: safeErrorText(error) })
  }
}

async function downloadExport(job: DashboardExport) {
  try {
    await deliveryService.downloadExport(job)
    ui.pushToast({ kind: 'success', title: 'Secure download started' })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Secure download failed', message: safeErrorText(error) })
  }
}

function scheduleInput() {
  const list = parseAddresses(recipients.value)
  if (!list.length) throw new Error('Enter at least one recipient')
  return {
    name: deliveryName.value,
    recipients: list,
    cc: parseAddresses(ccRecipients.value),
    bcc: parseAddresses(bccRecipients.value),
    subject: deliverySubject.value,
    format: deliveryFormat.value,
    schedule_type: deliveryCadence.value,
    schedule_expression: deliveryCadence.value === 'cron' ? deliveryCron.value.trim() : null,
    run_at: deliveryCadence.value === 'one_time' ? new Date(runAt.value).toISOString() : null,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
    include_dashboard_link: true,
  }
}

async function previewDelivery() {
  try {
    const input = scheduleInput()
    emailPreview.value = await deliveryService.preview(props.dashboard.id, input)
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Email preview unavailable', message: safeErrorText(error) })
  }
}

async function createDelivery() {
  try {
    await deliveryService.create(props.dashboard.id, scheduleInput())
    await refresh()
    ui.pushToast({ kind: 'success', title: 'Dashboard delivery scheduled' })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Delivery could not be scheduled', message: safeErrorText(error) })
  }
}

async function testDelivery(item: ScheduledDelivery) {
  try {
    await deliveryService.test(item.id)
    ui.pushToast({ kind: 'success', title: 'Test delivery queued' })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Test delivery could not be queued', message: safeErrorText(error) })
  }
}

async function showHistory(item: ScheduledDelivery) {
  try {
    deliveryRuns.value = { ...deliveryRuns.value, [item.id]: await deliveryService.history(item.id) }
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Delivery history unavailable', message: safeErrorText(error) })
  }
}

async function cancelDelivery(item: ScheduledDelivery) {
  if (!window.confirm(`Cancel “${item.name}”?`)) return
  try {
    await deliveryService.remove(item)
    delete deliveryRuns.value[item.id]
    await refresh()
    ui.pushToast({ kind: 'info', title: 'Delivery cancelled' })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Delivery could not be cancelled', message: safeErrorText(error) })
  }
}
</script>

<template>
  <VipDialog :open="open" title="Dashboard governance" :description="dashboard.name" size="lg" @close="emit('close')">
    <VipSegmented
      :model-value="tab"
      :options="[
        { value: 'versions', label: 'Versions', icon: 'history' },
        { value: 'sharing', label: 'Sharing', icon: 'users' },
        { value: 'snapshot', label: 'Snapshots', icon: 'image' },
        { value: 'export', label: 'Exports', icon: 'download' },
        { value: 'delivery', label: 'Delivery', icon: 'report' },
      ]"
      @update:model-value="tab = $event as typeof tab"
    />

    <div class="governance-body" :aria-busy="loading">
      <template v-if="tab === 'versions'">
        <p class="hint">Published versions are immutable. Restoring creates a new editable draft.</p>
        <div v-if="!versions.length" class="empty">No published versions yet.</div>
        <div v-for="version in versions" :key="version.id" class="record">
          <div>
            <strong>Version {{ version.version_number }}</strong>
            <div class="meta">
              {{ version.change_summary || 'No change summary' }} · {{ relativeTime(version.created_at) }}
            </div>
          </div>
          <VipBadge v-if="version.current_published" tone="success" size="sm">live</VipBadge>
          <VipButton v-else variant="tertiary" size="xs" @click="restore(version)">Restore</VipButton>
        </div>
      </template>

      <template v-else-if="tab === 'sharing'">
        <p class="hint">Grant additive viewer access to an active member of this workspace.</p>
        <div class="form-row">
          <VipInput
            v-model="principalId"
            label="Workspace user UUID"
            placeholder="00000000-0000-0000-0000-000000000000"
          /><VipButton variant="primary" @click="addShare">Grant view</VipButton>
        </div>
        <div v-if="!shares.filter((item) => !item.revoked_at).length" class="empty">No active direct shares.</div>
        <div v-for="share in shares.filter((item) => !item.revoked_at)" :key="share.id" class="record">
          <div>
            <strong>{{ share.principal_type }} · {{ share.permission_level }}</strong>
            <div class="meta">{{ share.principal_id }}</div>
          </div>
          <VipButton variant="ghost" size="xs" icon="trash" @click="revoke(share)">Revoke</VipButton>
        </div>
      </template>

      <template v-else-if="tab === 'snapshot'">
        <p class="hint">Capture a bounded reference to the currently published dashboard version.</p>
        <div class="form-row">
          <VipInput v-model="snapLabel" label="Snapshot label" placeholder="e.g. End of Q3" /><VipButton
            variant="primary"
            icon="image"
            @click="saveSnapshot"
            >Save snapshot</VipButton
          >
        </div>
        <div v-if="!snapshots.length" class="empty">No snapshots yet.</div>
        <div v-for="snapshot in snapshots" :key="snapshot.id" class="record">
          <div>
            <strong>{{ snapshot.name }}</strong>
            <div class="meta">{{ snapshot.status }} · {{ relativeTime(snapshot.created_at) }}</div>
          </div>
          <VipBadge tone="success" size="sm">{{ snapshot.status }}</VipBadge>
        </div>
      </template>

      <template v-else-if="tab === 'export'">
        <p class="hint">Exports run asynchronously from the immutable published dashboard version.</p>
        <div v-if="!canExport" class="notice notice--warning" role="status">
          Publish this dashboard to enable PDF, PNG, JSON and CSV exports. Exports always render the latest published
          version.
        </div>
        <div class="form-row">
          <VipSelect
            v-model="exportFormat"
            label="Format"
            :disabled="!canExport"
            :options="[
              { value: 'pdf', label: 'PDF' },
              { value: 'png', label: 'PNG image' },
              { value: 'json', label: 'JSON data' },
              { value: 'csv', label: 'CSV — all tables' },
            ]"
          />
          <VipButton
            variant="primary"
            icon="download"
            :disabled="!canExport"
            :title="canExport ? 'Queue a PDF/PNG/JSON/CSV export' : 'Publish the dashboard first'"
            @click="startExport"
            >Queue export</VipButton
          >
        </div>
        <div v-if="!exports.length" class="empty">No exports yet.</div>
        <div v-for="job in exports" :key="job.id" class="record export-record">
          <div>
            <strong>{{ job.format.toUpperCase() }} export</strong>
            <div class="meta">{{ job.status }} · {{ relativeTime(job.created_at) }}</div>
            <progress :value="job.progress" max="100" :aria-label="`${job.format} export progress`">
              {{ job.progress }}%
            </progress>
            <div v-if="job.safe_error_message" class="error-text">{{ job.safe_error_message }}</div>
          </div>
          <VipButton
            v-if="['queued', 'rendering'].includes(job.status)"
            variant="ghost"
            size="xs"
            @click="cancelExport(job)"
            >Cancel</VipButton
          >
          <VipButton
            v-else-if="['failed', 'cancelled'].includes(job.status)"
            variant="tertiary"
            size="xs"
            @click="retryExport(job)"
            >Retry</VipButton
          >
          <VipButton
            v-else-if="job.status === 'completed'"
            variant="primary"
            size="xs"
            icon="download"
            @click="downloadExport(job)"
            >Download</VipButton
          >
        </div>
      </template>

      <template v-else>
        <p class="hint">Email delivery uses a provider-backed server pipeline and immutable published versions.</p>
        <div class="delivery-grid">
          <VipInput v-model="deliveryName" label="Delivery name" />
          <VipInput v-model="deliverySubject" label="Email subject" />
          <VipInput v-model="recipients" label="Recipients" placeholder="finance@example.com, owner@example.com" />
          <VipInput v-model="ccRecipients" label="CC" placeholder="Optional comma-separated recipients" />
          <VipInput v-model="bccRecipients" label="BCC" placeholder="Optional comma-separated recipients" />
          <VipSelect
            v-model="deliveryFormat"
            label="Attachment"
            :options="[
              { value: 'pdf', label: 'PDF' },
              { value: 'png', label: 'PNG image' },
              { value: 'csv', label: 'CSV data' },
            ]"
          />
          <VipSelect
            v-model="deliveryCadence"
            label="Schedule"
            :options="[
              { value: 'one_time', label: 'One time' },
              { value: 'daily', label: 'Daily' },
              { value: 'weekly', label: 'Weekly' },
              { value: 'monthly', label: 'Monthly' },
              { value: 'cron', label: 'Cron schedule' },
            ]"
          />
          <VipInput v-if="deliveryCadence === 'one_time'" v-model="runAt" type="datetime-local" label="Run at" />
          <VipInput
            v-if="deliveryCadence === 'cron'"
            v-model="deliveryCron"
            label="Cron expression"
            help="Five fields: minute hour day-of-month month day-of-week"
          />
        </div>
        <div class="actions">
          <VipButton variant="tertiary" @click="previewDelivery">Preview email</VipButton
          ><VipButton variant="primary" @click="createDelivery">Schedule delivery</VipButton>
        </div>
        <iframe
          v-if="emailPreview"
          class="email-preview"
          title="Dashboard email preview"
          sandbox=""
          :srcdoc="emailPreview.html"
        />
        <div v-if="!deliveries.length" class="empty">No delivery schedules yet.</div>
        <div v-for="item in deliveries" :key="item.id" class="delivery-record">
          <div class="record">
            <div>
              <strong>{{ item.name }}</strong>
              <div class="meta">
                {{ item.schedule_type.replace('_', ' ') }} · {{ item.status
                }}<template v-if="item.next_run_at"> · {{ relativeTime(item.next_run_at) }}</template>
              </div>
              <div v-if="item.retry_count" class="error-text">
                {{ item.retry_count }} of {{ item.max_retries }} retries used
              </div>
            </div>
            <div class="record-actions">
              <VipButton variant="ghost" size="xs" @click="showHistory(item)">History</VipButton>
              <VipButton variant="tertiary" size="xs" @click="testDelivery(item)">Send test</VipButton>
              <VipButton variant="ghost" size="xs" @click="cancelDelivery(item)">Cancel</VipButton>
            </div>
          </div>
          <div v-if="deliveryRuns[item.id]" class="delivery-history">
            <div v-if="!deliveryRuns[item.id].length" class="meta">No delivery attempts yet.</div>
            <div v-for="run in deliveryRuns[item.id]" :key="run.id" class="history-row">
              <span>{{ relativeTime(run.created_at) }}</span>
              <VipBadge
                :tone="run.status === 'sent' ? 'success' : run.status === 'failed' ? 'danger' : 'neutral'"
                size="sm"
              >
                {{ run.status }}
              </VipBadge>
              <span v-if="run.safe_error_message" class="error-text">{{ run.safe_error_message }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <template #footer><VipButton variant="tertiary" @click="emit('close')">Close</VipButton></template>
  </VipDialog>
</template>

<style scoped>
.governance-body {
  margin-top: var(--vip-sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.hint,
.meta,
.empty {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.empty {
  padding: var(--vip-sp-5);
  text-align: center;
}
.notice {
  margin-bottom: var(--vip-sp-4);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  border-radius: var(--vip-radius-md);
  font-size: var(--vip-fs-sm);
  border: 1px solid var(--vip-border);
  background: var(--vip-surface-2);
  color: var(--vip-text-secondary);
}
.notice--warning {
  border-color: var(--vip-warning);
  background: var(--vip-warning-soft, var(--vip-surface-2));
  color: var(--vip-text-primary);
}
.form-row,
.actions {
  display: flex;
  align-items: flex-end;
  gap: var(--vip-sp-3);
  margin-bottom: var(--vip-sp-3);
}
.form-row > :first-child {
  flex: 1;
}
.actions {
  justify-content: flex-end;
}
.record {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-4);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-2);
}
.record > :first-child {
  flex: 1;
  min-width: 0;
}
.record-actions {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
}
.delivery-record {
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
}
.delivery-record .record {
  border: 0;
}
.delivery-history {
  padding: 0 var(--vip-sp-5) var(--vip-sp-4);
}
.history-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) auto minmax(0, 2fr);
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-2) 0;
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.meta {
  margin-top: 2px;
  overflow-wrap: anywhere;
}
.delivery-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--vip-sp-3);
}
.email-preview {
  width: 100%;
  min-height: 220px;
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  background: white;
}
progress {
  width: 100%;
  height: 8px;
  margin-top: var(--vip-sp-2);
  accent-color: var(--vip-brand-500);
}
.error-text {
  margin-top: var(--vip-sp-2);
  color: var(--vip-danger-text);
  font-size: var(--vip-fs-xs);
}
@media (max-width: 720px) {
  .form-row,
  .actions {
    align-items: stretch;
    flex-direction: column;
  }
  .delivery-grid {
    grid-template-columns: 1fr;
  }
  .record {
    align-items: flex-start;
    flex-wrap: wrap;
  }
}
</style>
