<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Dashboard } from '@/shared/types/dashboard'
import { toQuery } from '@/shared/types/dashboard'
import { deliveryService, type DeliveryCadence, type DeliveryFormat, type ScheduledDelivery } from './delivery.service'
import { semanticService } from '@/shared/services/semanticModels'
import { useUiStore } from '@/shared/stores/ui'
import { downloadJson, downloadCsv, downloadText, slug } from '@/shared/lib/download'
import { relativeTime } from '@/shared/lib/format'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const props = defineProps<{ open: boolean; dashboard: Dashboard; initialTab?: 'export' | 'snapshot' | 'email' }>()
const emit = defineEmits<{ close: [] }>()
const ui = useUiStore()

const tab = ref<'export' | 'snapshot' | 'email'>('export')
watch(
  () => props.open,
  (o) => {
    if (o) tab.value = props.initialTab ?? 'export'
  },
)

/* ---- export ---- */
const exporting = ref(false)

async function doExport(format: 'json' | 'csv' | 'pdf' | 'png') {
  exporting.value = true
  try {
    const base = slug(props.dashboard.name)
    if (format === 'json') {
      downloadJson(`${base}.json`, props.dashboard)
    } else if (format === 'csv') {
      // Export the first data-bound widget's query result as CSV.
      const widget = props.dashboard.pages
        .flatMap((p) => p.widgets)
        .find((w) => w.modelId && !['text', 'rich-text', 'image', 'filter', 'date-filter'].includes(w.type))
      if (widget) {
        const result = await semanticService.query(toQuery(widget))
        downloadCsv(
          `${base}.csv`,
          result.columns.map((c) => c.label),
          result.rows.map((r) => result.columns.map((c) => r[c.key])),
        )
      } else {
        downloadCsv(
          `${base}.csv`,
          ['Widget', 'Type'],
          props.dashboard.pages.flatMap((p) => p.widgets).map((w) => [w.general.name, w.type]),
        )
      }
    } else {
      // PDF/PNG are server-rendered; provide a portable manifest download now.
      const manifest = `VIP dashboard export (${format.toUpperCase()})\nDashboard: ${props.dashboard.name}\nPages: ${props.dashboard.pages.length}\nWidgets: ${props.dashboard.pages.reduce((s, p) => s + p.widgets.length, 0)}\nExported: ${new Date().toISOString()}\n\nNote: pixel-perfect ${format.toUpperCase()} rendering is produced by the backend rendering service.`
      downloadText(`${base}.${format}.txt`, manifest)
    }
    ui.pushToast({ kind: 'success', title: `Exported as ${format.toUpperCase()}`, message: 'Download started.' })
  } finally {
    exporting.value = false
  }
}

/* ---- snapshot ---- */
const snapLabel = ref('')
const savingSnap = ref(false)
async function saveSnapshot() {
  savingSnap.value = true
  await deliveryService.createSnapshot(
    props.dashboard.id,
    snapLabel.value || `Snapshot ${new Date().toLocaleDateString()}`,
    props.dashboard.pages.length,
  )
  savingSnap.value = false
  snapLabel.value = ''
  ui.pushToast({ kind: 'success', title: 'Snapshot saved', message: 'A point-in-time copy is now available.' })
}

/* ---- email delivery ---- */
const recipients = ref('')
const subject = ref(`${props.dashboard.name} — scheduled report`)
const format = ref<DeliveryFormat>('pdf')
const cadence = ref<DeliveryCadence>('weekly')
const creating = ref(false)
const emailError = ref('')

function validEmails(): string[] {
  return recipients.value
    .split(/[,;\s]+/)
    .map((e) => e.trim())
    .filter(Boolean)
}
async function createDelivery() {
  const list = validEmails()
  emailError.value = ''
  if (!list.length) {
    emailError.value = 'Add at least one recipient.'
    return
  }
  if (list.some((e) => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e))) {
    emailError.value = 'One or more email addresses look invalid.'
    return
  }
  creating.value = true
  const created = await deliveryService.create({
    dashboardId: props.dashboard.id,
    dashboardName: props.dashboard.name,
    recipients: list,
    format: format.value,
    cadence: cadence.value,
    subject: subject.value,
  })
  creating.value = false
  recipients.value = ''
  ui.pushToast({
    kind: 'success',
    title: 'Delivery scheduled',
    message: `${created.recipients.length} recipient(s) · ${created.cadence}`,
  })
  refreshDeliveries()
}

const deliveries = ref<ScheduledDelivery[]>([])
async function refreshDeliveries() {
  deliveries.value = (await deliveryService.list()).filter((d) => d.dashboardId === props.dashboard.id)
}
watch(
  () => props.open,
  (o) => {
    if (o) refreshDeliveries()
  },
)
async function removeDelivery(id: string) {
  await deliveryService.remove(id)
  refreshDeliveries()
  ui.pushToast({ kind: 'info', title: 'Delivery removed' })
}
</script>

<template>
  <VipDialog :open="open" title="Share & deliver" :description="dashboard.name" size="lg" @close="emit('close')">
    <VipSegmented
      :model-value="tab"
      :options="[
        { value: 'export', label: 'Export', icon: 'download' },
        { value: 'snapshot', label: 'Snapshot', icon: 'image' },
        { value: 'email', label: 'Email delivery', icon: 'report' },
      ]"
      @update:model-value="tab = $event as typeof tab"
    />

    <div class="sd__body">
      <!-- EXPORT -->
      <template v-if="tab === 'export'">
        <p class="sd__hint">
          Download the current dashboard. JSON and CSV are generated in your browser; PDF and PNG are produced by the
          rendering service.
        </p>
        <div class="sd__export-grid">
          <button class="sd__export" :disabled="exporting" @click="doExport('pdf')">
            <VipIcon name="report" :size="20" /><span>PDF</span>
          </button>
          <button class="sd__export" :disabled="exporting" @click="doExport('png')">
            <VipIcon name="image" :size="20" /><span>PNG</span>
          </button>
          <button class="sd__export" :disabled="exporting" @click="doExport('csv')">
            <VipIcon name="table" :size="20" /><span>CSV data</span>
          </button>
          <button class="sd__export" :disabled="exporting" @click="doExport('json')">
            <VipIcon name="code" :size="20" /><span>JSON definition</span>
          </button>
        </div>
      </template>

      <!-- SNAPSHOT -->
      <template v-else-if="tab === 'snapshot'">
        <p class="sd__hint">Capture a point-in-time copy of the dashboard and its data for audit or comparison.</p>
        <div class="sd__row">
          <VipInput v-model="snapLabel" label="Snapshot label" placeholder="e.g. End of Q3" />
          <VipButton variant="primary" icon="image" :loading="savingSnap" @click="saveSnapshot"
            >Save snapshot</VipButton
          >
        </div>
      </template>

      <!-- EMAIL -->
      <template v-else>
        <p class="sd__hint">
          Schedule this dashboard to be emailed to recipients. No mail is sent from the browser — the backend delivery
          service handles sending.
        </p>
        <VipInput
          v-model="recipients"
          label="Recipients"
          placeholder="alice@company.com, team@company.com"
          icon="users"
          :error="emailError"
          help="Comma or space separated."
        />
        <VipInput v-model="subject" label="Subject" />
        <div class="sd__row2">
          <VipSelect
            v-model="format"
            label="Format"
            :options="[
              { value: 'pdf', label: 'PDF' },
              { value: 'png', label: 'PNG' },
              { value: 'excel', label: 'Excel' },
              { value: 'csv', label: 'CSV' },
            ]"
          />
          <VipSelect
            v-model="cadence"
            label="Cadence"
            :options="[
              { value: 'once', label: 'Once' },
              { value: 'daily', label: 'Daily' },
              { value: 'weekly', label: 'Weekly' },
              { value: 'monthly', label: 'Monthly' },
            ]"
          />
        </div>
        <VipButton variant="primary" icon="calendar" :loading="creating" @click="createDelivery"
          >Schedule delivery</VipButton
        >

        <div v-if="deliveries.length" class="sd__deliveries">
          <div class="sd__section">Scheduled deliveries</div>
          <div v-for="d in deliveries" :key="d.id" class="sd__delivery">
            <div class="sd__delivery-main">
              <div class="sd__delivery-subject">{{ d.subject }}</div>
              <div class="sd__delivery-meta">
                {{ d.recipients.length }} recipient(s) · {{ d.format.toUpperCase() }} · {{ d.cadence }} · next
                {{ relativeTime(d.nextRun) }}
              </div>
            </div>
            <VipBadge :tone="d.active ? 'success' : 'neutral'" size="sm">{{ d.active ? 'active' : 'paused' }}</VipBadge>
            <VipButton variant="ghost" size="xs" icon="trash" @click="removeDelivery(d.id)" />
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <VipButton variant="tertiary" @click="emit('close')">Close</VipButton>
    </template>
  </VipDialog>
</template>

<style scoped>
.sd__body {
  margin-top: var(--vip-sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.sd__hint {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.sd__export-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--vip-sp-4);
}
.sd__export {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-7) var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-sm);
}
.sd__export:hover:not(:disabled) {
  border-color: var(--vip-brand-500);
  color: var(--vip-brand-text);
  background: var(--vip-brand-soft);
}
.sd__export:disabled {
  opacity: 0.5;
}
.sd__row {
  display: flex;
  gap: var(--vip-sp-4);
  align-items: flex-end;
}
.sd__row > :first-child {
  flex: 1;
}
.sd__row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-4);
}
.sd__deliveries {
  margin-top: var(--vip-sp-4);
}
.sd__section {
  font-size: var(--vip-fs-2xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-disabled);
  margin-bottom: var(--vip-sp-3);
}
.sd__delivery {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  margin-bottom: var(--vip-sp-2);
}
.sd__delivery-main {
  flex: 1;
  min-width: 0;
}
.sd__delivery-subject {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
}
.sd__delivery-meta {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  margin-top: 2px;
}
</style>
