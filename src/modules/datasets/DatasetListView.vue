<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { relativeTime, formatNumber } from '@/shared/lib/format'
import { datasetService, type Dataset, type DatasetStatus } from './datasets.service'
import { connectionService } from '@/modules/connections/connections.service'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipCheckbox from '@/shared/ui/VipCheckbox.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTooltip from '@/shared/ui/VipTooltip.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipTextarea from '@/shared/ui/VipTextarea.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipConfirmDialog from '@/shared/ui/VipConfirmDialog.vue'
import { safeErrorText } from '@/shared/lib/safeError'
import { platformInfrastructure } from '@/shared/services/platformInfrastructure'
import {
  isLegacyXlsFilename,
  isXlsxFilename,
  loadFileFormatCapabilities,
  tabularAcceptAttribute,
} from '@/shared/lib/fileFormats'

const router = useRouter()
const platform = usePlatformStore()
const ui = useUiStore()

const data = ref<Dataset[]>([])
const isLoading = ref(false)
const listError = ref('')
const page = ref(1)
const PAGE_SIZE_OPTIONS = [25, 50, 100] as const
const pageSize = ref(50)
const pageSizeOptions = PAGE_SIZE_OPTIONS.map((n) => ({ value: String(n), label: `${n} / page` }))
const pageSizeModel = computed<string>({
  get: () => String(pageSize.value),
  set: (value) => {
    pageSize.value = Number(value)
  },
})
const total = ref(0)
let listRequest = 0
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const rangeStart = computed(() => (total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1))
const rangeEnd = computed(() => Math.min(page.value * pageSize.value, total.value))
const { data: connections } = useQuery('datasets:connections', async () => (await connectionService.list(1, 100)).items)
const canDiscover = computed(() => platform.can('dataset.discover'))
const discoverOpen = ref(false)
const dialogMode = ref<'discover' | 'csv'>('discover')
const discoverBusy = ref(false)
const discoverError = ref('')
const discovery = reactive({ connectionId: '', schemas: 'public', names: '*' })
const csvImport = reactive({
  connectionId: '',
  schema: 'vip_data',
  table: '',
  displayName: '',
  description: '',
  content: '',
})
const csvFileName = ref('')
const csvFileInput = ref<HTMLInputElement>()
/** Binary workbook selected for server-side XLSX ingest (not pasted into the textarea). */
const xlsxFile = ref<File | null>(null)
const tabularAccept = ref(tabularAcceptAttribute())

onMounted(() => {
  void loadFileFormatCapabilities()
    .then((capabilities) => {
      tabularAccept.value = tabularAcceptAttribute(capabilities)
    })
    .catch(() => {
      /* keep CSV/XLSX defaults when capabilities cannot be loaded */
    })
})

function triggerCsvFilePicker(): void {
  csvFileInput.value?.click()
}

async function onCsvFileSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  discoverError.value = ''
  xlsxFile.value = null
  const name = file.name
  const lower = name.toLowerCase()
  if (isLegacyXlsFilename(name)) {
    input.value = ''
    discoverError.value = 'Legacy .xls workbooks are not supported. Save as .xlsx or CSV UTF-8, then upload again.'
    return
  }
  if (isXlsxFilename(name) || file.type.includes('spreadsheetml')) {
    if (file.size > 5 * 1024 * 1024) {
      input.value = ''
      discoverError.value = 'Interactive XLSX import is limited to 5 MB.'
      return
    }
    xlsxFile.value = file
    csvImport.content = ''
    csvFileName.value = name
    const base = name.replace(/\.[^.]+$/, '')
    if (!csvImport.displayName.trim()) csvImport.displayName = base
    if (!csvImport.table.trim()) {
      csvImport.table =
        base
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '_')
          .replace(/^_+|_+$/g, '')
          .slice(0, 60) || 'imported_table'
    }
    input.value = ''
    return
  }
  const hasDelimitedTextExtension = lower.endsWith('.csv') || lower.endsWith('.tsv') || lower.endsWith('.txt')
  if (!hasDelimitedTextExtension) {
    input.value = ''
    discoverError.value = 'Supported tabular uploads are CSV, TSV, TXT, and XLSX.'
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    input.value = ''
    discoverError.value = 'The file is larger than 10 MB. Import a smaller extract or split it.'
    return
  }
  try {
    const raw = await file.text()
    let text = raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw // strip UTF-8 BOM
    if (lower.endsWith('.tsv')) {
      // Convert tab-separated values to CSV so the backend ingest sees commas.
      text = text
        .split(/\r?\n/)
        .map((line) =>
          line
            .split('\t')
            .map((cell) => (/[",\n]/.test(cell) ? `"${cell.replace(/"/g, '""')}"` : cell))
            .join(','),
        )
        .join('\n')
    }
    if (!text.trim()) {
      input.value = ''
      discoverError.value = 'The selected file is empty.'
      return
    }
    csvImport.content = text
    csvFileName.value = name
    const base = name.replace(/\.[^.]+$/, '')
    if (!csvImport.displayName.trim()) csvImport.displayName = base
    if (!csvImport.table.trim()) {
      csvImport.table =
        base
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '_')
          .replace(/^_+|_+$/g, '')
          .slice(0, 60) || 'imported_table'
    }
    input.value = ''
  } catch {
    input.value = ''
    discoverError.value = 'The file could not be read. Ensure it is a UTF-8 encoded CSV file.'
  }
}
const connectionOptions = computed(() =>
  (connections.value ?? [])
    .filter((item) => item.status === 'active')
    .map((item) => ({ value: item.id, label: `${item.name} · ${item.type.name}` })),
)
// Safe default: preselect only when exactly ONE eligible connection exists. With
// zero or multiple, selection stays empty so the user must choose explicitly —
// never an implicit "first active connection" that depends on API ordering.
function safeDefaultConnectionId(): string {
  return connectionOptions.value.length === 1 ? connectionOptions.value[0].value : ''
}
const connectionHelp = computed(() => {
  if (connectionOptions.value.length === 1) return 'Automatically selected — the only eligible connection.'
  if (connectionOptions.value.length > 1) return 'Choose the connection to import into.'
  return undefined
})
// Clear a selection that is no longer valid (workspace switch, or the connection
// was deactivated) rather than silently importing against a different one.
watch(connectionOptions, (options) => {
  const ids = new Set(options.map((option) => option.value))
  if (csvImport.connectionId && !ids.has(csvImport.connectionId)) csvImport.connectionId = ''
  if (discovery.connectionId && !ids.has(discovery.connectionId)) discovery.connectionId = ''
})
const dialogConnectionId = computed({
  get: () => (dialogMode.value === 'csv' ? csvImport.connectionId : discovery.connectionId),
  set: (value: string) => {
    if (dialogMode.value === 'csv') csvImport.connectionId = value
    else discovery.connectionId = value
  },
})

function openDiscovery(): void {
  dialogMode.value = 'discover'
  discovery.connectionId = safeDefaultConnectionId()
  discoverError.value = ''
  discoverOpen.value = true
}

function openCsvImport(): void {
  dialogMode.value = 'csv'
  csvImport.connectionId = safeDefaultConnectionId()
  csvImport.schema = 'vip_data'
  csvImport.table = ''
  csvImport.displayName = ''
  csvImport.description = ''
  csvImport.content = ''
  csvFileName.value = ''
  xlsxFile.value = null
  discoverError.value = ''
  discoverOpen.value = true
}

async function discover(): Promise<void> {
  const connectionId = dialogMode.value === 'csv' ? csvImport.connectionId : discovery.connectionId
  if (!connectionId) {
    discoverError.value = 'Select a connection.'
    return
  }
  if (dialogMode.value === 'csv' && !xlsxFile.value && !csvImport.content.trim()) {
    discoverError.value = 'Upload a CSV/TSV/TXT/XLSX file or paste CSV data.'
    return
  }
  discoverBusy.value = true
  discoverError.value = ''
  try {
    let result: { discovered: number; persisted: number; warnings: string[] }
    if (dialogMode.value === 'csv' && xlsxFile.value) {
      const uploaded = await platformInfrastructure.upload(xlsxFile.value)
      result = await datasetService.ingestFile({
        fileId: uploaded.id,
        connectionId: csvImport.connectionId,
        schema: csvImport.schema.trim(),
        table: csvImport.table.trim(),
        displayName: csvImport.displayName.trim(),
        description: csvImport.description.trim(),
      })
    } else if (dialogMode.value === 'csv') {
      result = await datasetService.ingestCsv({
        connectionId: csvImport.connectionId,
        schema: csvImport.schema.trim(),
        table: csvImport.table.trim(),
        displayName: csvImport.displayName.trim(),
        description: csvImport.description.trim(),
        csvContent: csvImport.content,
      })
    } else {
      result = await datasetService.discover({
        connectionId: discovery.connectionId,
        schemas: discovery.schemas
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        includeNames: discovery.names
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      })
    }
    await refetch()
    discoverOpen.value = false
    ui.pushToast({
      kind: 'success',
      title: 'Discovery completed',
      message: `${result.persisted} of ${result.discovered} objects persisted.`,
    })
  } catch (cause) {
    discoverError.value = (cause as Error).message
  } finally {
    discoverBusy.value = false
  }
}

const search = ref('')
const statusFilter = ref<'all' | DatasetStatus>('all')
const certifiedOnly = ref(false)

async function refetch(): Promise<void> {
  const request = ++listRequest
  isLoading.value = true
  listError.value = ''
  try {
    const status =
      statusFilter.value === 'all'
        ? undefined
        : statusFilter.value === 'building'
          ? 'inactive'
          : statusFilter.value === 'deprecated'
            ? 'archived'
            : statusFilter.value
    const result = await datasetService.listPage({
      page: page.value,
      pageSize: pageSize.value,
      search: search.value,
      status,
    })
    if (request !== listRequest) return
    data.value = result.items
    total.value = result.total
  } catch (cause) {
    if (request !== listRequest) return
    listError.value = safeErrorText(cause)
  } finally {
    if (request === listRequest) isLoading.value = false
  }
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    if (page.value !== 1) page.value = 1
    else void refetch()
  }, 300)
})
watch(statusFilter, () => {
  if (page.value !== 1) page.value = 1
  else void refetch()
})
// Changing page size re-anchors to page 1 so the visible window stays valid.
watch(pageSize, () => {
  if (page.value !== 1) page.value = 1
  else void refetch()
})
watch(page, () => void refetch())
onMounted(() => void refetch())
onBeforeUnmount(() => clearTimeout(searchTimer))

const statusOptions: { value: string; label: string }[] = [
  { value: 'all', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'building', label: 'Building' },
  { value: 'deprecated', label: 'Deprecated' },
]

const rows = computed<Dataset[]>(() => {
  return (data.value ?? []).filter((d) => {
    const matchesCertified = !certifiedOnly.value || d.certified
    return matchesCertified
  })
})

const STATUS_TONE: Record<DatasetStatus, 'success' | 'info' | 'neutral'> = {
  active: 'success',
  building: 'info',
  deprecated: 'neutral',
}

function qualityTone(score: number | null): 'success' | 'warning' | 'danger' {
  if (score == null) return 'warning'
  if (score >= 90) return 'success'
  if (score >= 75) return 'warning'
  return 'danger'
}

const canArchive = computed(() => platform.can('dataset.archive'))
const canDelete = computed(() => platform.can('dataset.delete'))
const columns = computed<Column<Dataset>[]>(() => [
  { key: 'name', label: 'Dataset', width: '32%' },
  { key: 'owner', label: 'Owner' },
  { key: 'rowCount', label: 'Rows', align: 'right' },
  { key: 'qualityScore', label: 'Quality', align: 'right' },
  { key: 'freshness', label: 'Freshness', align: 'right' },
  { key: 'status', label: 'Status' },
  ...(canArchive.value || canDelete.value ? [{ key: 'actions', label: '', align: 'right' as const }] : []),
])

function open(row: Dataset) {
  router.push(`/datasets/${row.id}`)
}

// --- Archive / delete lifecycle (both soft-archive metadata server-side; no restore) ---
const lifecycle = ref<{ kind: 'archive' | 'delete'; row: Dataset } | null>(null)
const lifecyclePending = ref(false)
const lifecycleError = ref<string | null>(null)

function rowMenu() {
  return [
    ...(canArchive.value ? [{ key: 'archive', label: 'Archive', icon: 'archive', danger: true }] : []),
    ...(canDelete.value ? [{ key: 'delete', label: 'Delete', icon: 'trash', danger: true }] : []),
  ]
}
function onRowMenu(row: Dataset, key: string) {
  if (key === 'archive' || key === 'delete') {
    lifecycleError.value = null
    lifecycle.value = { kind: key, row }
  }
}
function closeLifecycle() {
  if (lifecyclePending.value) return
  lifecycle.value = null
  lifecycleError.value = null
}
const lifecycleDialog = computed(() => {
  const ctx = lifecycle.value
  if (!ctx) return null
  const shared = {
    resourceName: ctx.row.name,
    impact: [
      `Owner: ${ctx.row.owner} · ${formatNumber(ctx.row.rowCount, { style: 'compact' })} rows`,
      'Pipelines, semantic models, metrics and dashboards that use it may break.',
      'This archives the dataset metadata only — the underlying source data is not deleted.',
    ],
    note: 'Not reversible from the UI — no restore endpoint is available.',
  }
  return ctx.kind === 'archive'
    ? {
        ...shared,
        level: 'warning' as const,
        title: 'Archive dataset?',
        message: 'This dataset will be removed from the active dataset catalog.',
        confirmLabel: 'Archive',
        requireTyping: false,
      }
    : {
        ...shared,
        level: 'danger' as const,
        title: 'Delete dataset?',
        message: 'Delete is an elevated, audited action that removes this dataset from the catalog.',
        confirmLabel: 'Delete',
        requireTyping: true,
      }
})
async function confirmLifecycle() {
  const ctx = lifecycle.value
  if (!ctx) return
  lifecyclePending.value = true
  lifecycleError.value = null
  try {
    if (ctx.kind === 'archive') await datasetService.archive(ctx.row.id)
    else await datasetService.remove(ctx.row.id)
    ui.pushToast({
      kind: 'success',
      title: ctx.kind === 'archive' ? 'Dataset archived' : 'Dataset deleted',
      message: ctx.row.name,
    })
    lifecycle.value = null
    await refetch()
  } catch (e) {
    lifecycleError.value = safeErrorText(e)
  } finally {
    lifecyclePending.value = false
  }
}
</script>

<template>
  <div class="dl">
    <VipPageHeader title="Datasets" description="Browse the certified and in-progress datasets across your workspaces.">
      <template #actions>
        <VipButton variant="primary" icon="search" :disabled="!canDiscover" @click="openDiscovery">
          Discover datasets
        </VipButton>
        <VipButton variant="secondary" icon="upload" :disabled="!canDiscover" @click="openCsvImport">
          Import CSV
        </VipButton>
      </template>
    </VipPageHeader>

    <VipCard :padded="false">
      <div class="dl__toolbar">
        <div class="dl__search">
          <VipInput v-model="search" icon="search" size="sm" placeholder="Search dataset name or source" />
        </div>
        <div class="dl__filters">
          <VipSelect v-model="statusFilter" :options="statusOptions" aria-label="Dataset status" size="sm" />
          <VipCheckbox v-model="certifiedOnly" label="Certified only" />
          <span class="dl__count">{{ rows.length }} of {{ total }}</span>
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
          <VipBadge :tone="qualityTone(row.qualityScore)" variant="soft" size="sm">{{
            row.qualityScore == null ? 'Not evaluated' : row.qualityScore
          }}</VipBadge>
        </template>

        <template #cell-freshness="{ row }">
          <span class="dl__muted">{{ relativeTime(row.freshness) }}</span>
        </template>

        <template #cell-status="{ row }">
          <VipBadge :tone="STATUS_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge>
        </template>

        <template #cell-actions="{ row }">
          <div class="dl__actions" @click.stop>
            <VipMenu :items="rowMenu()" align="end" @select="onRowMenu(row, $event)">
              <template #trigger>
                <button class="dl__menu" :aria-label="`Actions for ${row.name}`">
                  <VipIcon name="dotsV" :size="16" />
                </button>
              </template>
            </VipMenu>
          </div>
        </template>
      </VipTable>
      <div v-if="listError" class="dl__list-error" role="alert">
        {{ listError }} <button @click="refetch">Retry</button>
      </div>
      <div v-if="total > 0" class="dl__paging" role="navigation" aria-label="Dataset catalog pages">
        <span class="dl__range" aria-live="polite">
          Showing {{ rangeStart }}&ndash;{{ rangeEnd }} of {{ total }} datasets
        </span>
        <div class="dl__paging-controls">
          <VipSelect
            v-model="pageSizeModel"
            :options="pageSizeOptions"
            aria-label="Datasets per page"
            size="sm"
            class="dl__page-size"
          />
          <VipButton size="xs" :disabled="page === 1 || isLoading" aria-label="Previous page" @click="page--"
            >Previous</VipButton
          >
          <span class="dl__page-of">Page {{ page }} of {{ totalPages }}</span>
          <VipButton size="xs" :disabled="page >= totalPages || isLoading" aria-label="Next page" @click="page++"
            >Next</VipButton
          >
        </div>
      </div>
    </VipCard>

    <VipConfirmDialog
      v-if="lifecycleDialog"
      :open="!!lifecycle"
      :level="lifecycleDialog.level"
      :title="lifecycleDialog.title"
      :resource-name="lifecycleDialog.resourceName"
      :message="lifecycleDialog.message"
      :impact="lifecycleDialog.impact"
      :note="lifecycleDialog.note"
      :confirm-label="lifecycleDialog.confirmLabel"
      :require-typing="lifecycleDialog.requireTyping"
      :pending="lifecyclePending"
      :error="lifecycleError"
      @confirm="confirmLifecycle"
      @cancel="closeLifecycle"
    />
    <VipDialog
      :open="discoverOpen"
      :title="dialogMode === 'csv' ? 'Import CSV dataset' : 'Discover datasets'"
      :description="
        dialogMode === 'csv'
          ? 'Create a governed PostgreSQL table from deterministic CSV data.'
          : 'Inspect a live connection and persist selected governed objects.'
      "
      @close="discoverOpen = false"
    >
      <div class="discovery-form">
        <p v-if="connectionOptions.length === 0" class="discovery-empty" role="alert">
          No eligible connections available. Create or activate a connection before importing.
        </p>
        <VipSelect
          v-else
          v-model="dialogConnectionId"
          label="Connection"
          :options="connectionOptions"
          placeholder="Select a connection"
          required
          :help="connectionHelp"
        />
        <template v-if="dialogMode === 'discover'">
          <VipInput v-model="discovery.schemas" label="Schemas" help="Comma-separated schema names." />
          <VipInput
            v-model="discovery.names"
            label="Object name patterns"
            help="Comma-separated exact names or wildcard patterns."
          />
        </template>
        <template v-else>
          <VipInput v-model="csvImport.schema" label="Target schema" required />
          <VipInput
            v-model="csvImport.table"
            label="Target table"
            required
            help="Lowercase letters, numbers, and underscores."
          />
          <VipInput v-model="csvImport.displayName" label="Display name" />
          <VipInput v-model="csvImport.description" label="Description" />
          <div class="csv-upload">
            <VipButton type="button" variant="secondary" icon="upload" @click="triggerCsvFilePicker">
              Upload CSV or XLSX…
            </VipButton>
            <span v-if="csvFileName" class="csv-upload__name"
              ><VipIcon name="check" :size="14" /> {{ csvFileName }}</span
            >
            <span v-else class="csv-upload__hint"
              >Choose a .csv, .tsv, .txt, or .xlsx file from your device, or paste CSV below.</span
            >
            <input
              ref="csvFileInput"
              type="file"
              :accept="tabularAccept"
              class="csv-upload__input"
              aria-label="Upload CSV or XLSX file from your device"
              @change="onCsvFileSelected"
            />
          </div>
          <VipTextarea
            v-if="!xlsxFile"
            v-model="csvImport.content"
            label="CSV data"
            :rows="10"
            :required="!xlsxFile"
            help="Uploaded file contents appear here. The first row must contain unique field names."
          />
          <p v-else class="csv-upload__hint">
            XLSX selected — the first worksheet will be imported server-side after malware scan.
          </p>
        </template>
        <p v-if="discoverError" role="alert">{{ discoverError }}</p>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="discoverOpen = false">Cancel</VipButton>
        <VipButton
          variant="primary"
          :loading="discoverBusy"
          :disabled="connectionOptions.length === 0 || !dialogConnectionId"
          @click="discover"
        >
          {{ dialogMode === 'csv' ? 'Import and catalog' : 'Discover and persist' }}
        </VipButton>
      </template>
    </VipDialog>
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
.dl__paging,
.dl__list-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--vip-sp-4) var(--vip-sp-6);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  border-top: 1px solid var(--vip-border-subtle);
}
.dl__paging {
  gap: var(--vip-sp-4);
  flex-wrap: wrap;
}
.dl__paging-controls {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  flex-wrap: wrap;
}
.dl__page-size {
  min-width: 96px;
}
.dl__page-of {
  white-space: nowrap;
}
.dl__range {
  white-space: nowrap;
}
@media (max-width: 480px) {
  .dl__paging {
    justify-content: center;
  }
  .dl__range {
    width: 100%;
    text-align: center;
  }
}
.dl__list-error {
  justify-content: flex-start;
  gap: var(--vip-sp-2);
  color: var(--vip-danger-text);
}
.dl__list-error button {
  color: inherit;
  text-decoration: underline;
  background: none;
  border: 0;
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
.dl__actions {
  display: flex;
  justify-content: flex-end;
}
.dl__menu {
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
.dl__menu:hover {
  background: var(--vip-surface-hover);
  border-color: var(--vip-border);
  color: var(--vip-text-primary);
}
.discovery-form {
  display: grid;
  gap: var(--vip-sp-5);
}
.discovery-empty {
  padding: var(--vip-sp-4) var(--vip-sp-5);
  background: var(--vip-warning-soft);
  color: var(--vip-warning-text);
  border-radius: var(--vip-radius-md);
  font-size: var(--vip-fs-sm);
}
.csv-upload {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--vip-sp-3);
}
.csv-upload__input {
  display: none;
}
.csv-upload__name {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-primary);
}
.csv-upload__hint {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
</style>
