<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  datasetService,
  type Dataset,
  type DatasetField,
  type DatasetPreview,
} from '@/modules/datasets/datasets.service'
import { connectionService, type Connection } from '@/modules/connections/connections.service'
import { platformInfrastructure, type PlatformFile } from '@/shared/services/platformInfrastructure'
import { usePlatformStore } from '@/shared/stores/platform'
import type { PipelineNode, SchemaColumn } from '@/shared/types/pipeline'
import type { DataType } from '@/shared/types/semantic'
import type { PipelineEditor } from './usePipelineEditor'
import VipButton from '@/shared/ui/VipButton.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'

const props = defineProps<{ editor: PipelineEditor; node: PipelineNode }>()
const platform = usePlatformStore()

const sourceType = ref(String(props.node.config.source_type ?? 'dataset'))
const datasets = ref<Dataset[]>([])
const connections = ref<Connection[]>([])
const uploadedFiles = ref<PlatformFile[]>([])
const fields = ref<DatasetField[]>([])
const preview = ref<DatasetPreview | null>(null)
const selectedId = ref(String(props.node.config.dataset_id ?? ''))
const search = ref('')
const connectionId = ref('')
const schemaName = ref('public')
const objectName = ref('')
const displayName = ref('')
const description = ref('')
const file = ref<File | null>(null)
const existingFileId = ref('')
const datasetPage = ref(1)
const datasetPageSize = 20
const datasetTotal = ref(0)
const datasetLoading = ref(false)
const datasetError = ref('')
const loading = ref(false)
const error = ref('')
const message = ref('')

const datasetOptions = computed(() =>
  [...(selectedId.value ? datasets.value.filter((item) => item.id === selectedId.value) : []), ...datasets.value]
    .filter((item, index, all) => all.findIndex((candidate) => candidate.id === item.id) === index)
    .map((item) => ({ value: item.id, label: `${item.name} — ${item.source}` })),
)
const fileOptions = computed(() =>
  uploadedFiles.value
    .filter((item) => item.status === 'ready' && item.extension.toLowerCase() === '.csv')
    .map((item) => ({ value: item.id, label: `${item.original_filename} (${Math.ceil(item.size_bytes / 1024)} KB)` })),
)
const connectionOptions = computed(() =>
  connections.value
    .filter((item) => item.status === 'active')
    .map((item) => ({ value: item.id, label: `${item.name} (${item.health_status})` })),
)

function dataType(value: string): DataType {
  const type = value.toLowerCase()
  if (type.includes('timestamp')) return 'datetime'
  if (type === 'date') return 'date'
  if (type.includes('bool')) return 'boolean'
  if (type.includes('int')) return 'integer'
  if (/(numeric|decimal|float|double|real)/.test(type)) return 'number'
  return 'string'
}

let datasetRequest = 0
async function refreshDatasets() {
  const request = ++datasetRequest
  datasetLoading.value = true
  datasetError.value = ''
  try {
    const result = await datasetService.listPage({
      page: datasetPage.value,
      pageSize: datasetPageSize,
      search: search.value,
    })
    if (request !== datasetRequest) return
    datasets.value = result.items
    datasetTotal.value = result.total
  } catch (cause) {
    if (request !== datasetRequest) return
    datasetError.value = cause instanceof Error ? cause.message : 'Datasets could not be loaded.'
  } finally {
    if (request === datasetRequest) datasetLoading.value = false
  }
}

async function refreshFiles() {
  uploadedFiles.value = (await platformInfrastructure.files({ limit: 100 })).items
}

async function ensureConnections() {
  if (connections.value.length) return
  connections.value = (await connectionService.list(1, 100)).items
}

async function ensureFiles() {
  await Promise.all([ensureConnections(), refreshFiles()])
}

async function selectDataset(id: string) {
  selectedId.value = id
  error.value = ''
  message.value = ''
  if (!id) return
  loading.value = true
  try {
    const [nextFields, nextPreview] = await Promise.all([
      datasetService.listFields(id),
      datasetService.preview(id, 1, 10),
    ])
    fields.value = nextFields
    preview.value = nextPreview
    const schema: SchemaColumn[] = nextFields.map((item) => ({ name: item.name, dataType: dataType(item.type) }))
    const selectedDataset = datasets.value.find((item) => item.id === id)
    props.editor.updateNodeSource(
      props.node.id,
      {
        source_type: sourceType.value,
        dataset_id: id,
        dataset_version: selectedDataset?.version ?? 1,
        columns: nextFields.map((item) => item.name),
        schema_snapshot: nextFields.map((item) => ({ name: item.name, type: item.type, nullable: item.nullable })),
        row_limit: Number(props.node.config.row_limit ?? 10000),
      },
      schema,
    )
    message.value = `Bound ${nextFields.length} fields to this source.`
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'The dataset could not be loaded.'
  } finally {
    loading.value = false
  }
}

async function discover() {
  error.value = ''
  message.value = ''
  loading.value = true
  try {
    await datasetService.discover({
      connectionId: connectionId.value,
      schemas: [schemaName.value],
      includeNames: objectName.value ? [objectName.value] : [],
    })
    await refreshDatasets()
    message.value = 'Discovery completed. Select the registered dataset below.'
    sourceType.value = 'dataset'
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Discovery failed.'
  } finally {
    loading.value = false
  }
}

function chooseFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] ?? null
  if (file.value && !objectName.value) {
    objectName.value = file.value.name
      .replace(/\.csv$/i, '')
      .toLowerCase()
      .replace(/[^a-z0-9_]/g, '_')
  }
}

async function uploadAndRegister() {
  if (!file.value) return
  error.value = ''
  message.value = ''
  loading.value = true
  try {
    const uploaded = await platformInfrastructure.upload(file.value)
    await registerFile(uploaded.id)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'The CSV could not be registered.'
  } finally {
    loading.value = false
  }
}

async function registerFile(fileId: string) {
  error.value = ''
  message.value = ''
  loading.value = true
  try {
    await datasetService.ingestFile({
      fileId,
      connectionId: connectionId.value,
      schema: schemaName.value,
      table: objectName.value,
      displayName: displayName.value || objectName.value,
      description: description.value,
    })
    await refreshDatasets()
    const registered = datasets.value.find((item) => item.name === (displayName.value || objectName.value))
    sourceType.value = 'dataset'
    if (registered) await selectDataset(registered.id)
    else message.value = 'CSV registered. Select it from the dataset list.'
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'The CSV could not be registered.'
  } finally {
    loading.value = false
  }
}

watch(sourceType, () => {
  error.value = ''
  message.value = ''
  if (sourceType.value === 'connection') void ensureConnections()
  if (sourceType.value === 'file') void ensureFiles()
})
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    if (datasetPage.value !== 1) datasetPage.value = 1
    else void refreshDatasets()
  }, 300)
})
watch(datasetPage, () => void refreshDatasets())
onBeforeUnmount(() => clearTimeout(searchTimer))

onMounted(async () => {
  await refreshDatasets()
  if (selectedId.value) {
    if (!datasets.value.some((item) => item.id === selectedId.value)) {
      const selected = await datasetService.get(selectedId.value)
      if (selected) datasets.value = [selected, ...datasets.value]
    }
    await selectDataset(selectedId.value)
  }
})
</script>

<template>
  <div class="source">
    <div class="source__scope" aria-label="Current data scope">
      <span><strong>Organization</strong>{{ platform.organization?.name ?? 'Not selected' }}</span>
      <span><strong>Workspace</strong>{{ platform.workspace?.name ?? 'Not selected' }}</span>
    </div>
    <VipSelect
      v-model="sourceType"
      label="Source type"
      :options="[
        { value: 'dataset', label: 'Governed dataset' },
        { value: 'connection', label: 'Database table or view' },
        { value: 'file', label: 'Upload CSV' },
      ]"
    />

    <template v-if="sourceType === 'connection'">
      <VipSelect
        v-model="connectionId"
        label="Connection"
        placeholder="Select an active connection"
        :options="connectionOptions"
      />
      <VipInput v-model="schemaName" label="Schema" required />
      <VipInput v-model="objectName" label="Table or view" help="Leave empty to discover all objects in the schema." />
      <VipButton :loading="loading" :disabled="!connectionId || !schemaName" @click="discover"
        >Discover source</VipButton
      >
    </template>

    <template v-else-if="sourceType === 'file'">
      <VipSelect
        v-model="connectionId"
        label="Destination connection"
        placeholder="Select PostgreSQL"
        :options="connectionOptions"
      />
      <VipInput v-model="schemaName" label="Destination schema" required />
      <VipInput v-model="objectName" label="Destination table" required />
      <VipInput v-model="displayName" label="Dataset name" />
      <VipInput v-model="description" label="Description" />
      <VipSelect
        v-model="existingFileId"
        label="Existing uploaded CSV"
        placeholder="Select a ready file"
        :options="fileOptions"
      />
      <VipButton
        variant="tertiary"
        :loading="loading"
        :disabled="!existingFileId || !connectionId || !schemaName || !objectName"
        @click="registerFile(existingFileId)"
        >Register selected file</VipButton
      >
      <label class="source__file-label" for="pipeline-source-file">CSV file</label>
      <input id="pipeline-source-file" class="source__file" type="file" accept=".csv,text/csv" @change="chooseFile" />
      <VipButton
        :loading="loading"
        :disabled="!file || !connectionId || !schemaName || !objectName"
        @click="uploadAndRegister"
        >Upload and register</VipButton
      >
    </template>

    <template v-if="sourceType === 'dataset'">
      <div class="source__heading">
        <span>Governed datasets</span>
        <VipButton size="xs" variant="tertiary" icon="refresh" :loading="datasetLoading" @click="refreshDatasets"
          >Refresh</VipButton
        >
      </div>
      <VipInput v-model="search" label="Search datasets" placeholder="Name or source" />
      <VipSelect
        :model-value="selectedId"
        label="Dataset"
        placeholder="Select a governed dataset"
        :options="datasetOptions"
        @update:model-value="selectDataset"
      />
      <div class="source__paging">
        <VipButton size="xs" :disabled="datasetPage === 1" @click="datasetPage--">Previous</VipButton>
        <span>Page {{ datasetPage }} of {{ Math.max(1, Math.ceil(datasetTotal / datasetPageSize)) }}</span>
        <VipButton size="xs" :disabled="datasetPage * datasetPageSize >= datasetTotal" @click="datasetPage++"
          >Next</VipButton
        >
      </div>
      <div v-if="datasets.find((item) => item.id === selectedId)" class="source__metadata">
        <template v-for="item in [datasets.find((entry) => entry.id === selectedId)!]" :key="item.id">
          <span><strong>Type</strong>{{ item.sourceType }}</span>
          <span><strong>Object</strong>{{ item.schema }}.{{ item.table }}</span>
          <span><strong>Rows</strong>{{ item.rowCount.toLocaleString() }}</span>
          <span><strong>Quality</strong>{{ item.qualityScore ?? 'Not evaluated' }}</span>
          <span><strong>Version</strong>{{ item.version }}</span>
          <span><strong>Access</strong>{{ item.readOnly ? 'Read-only' : 'Writable' }}</span>
        </template>
      </div>
    </template>

    <div v-if="loading || datasetLoading" class="source__state">
      <VipSpinner :size="18" label="Loading source…" />
    </div>
    <p v-if="datasetError" class="source__error" role="alert">
      {{ datasetError }} <button @click="refreshDatasets">Retry</button>
    </p>
    <p v-if="error" class="source__error" role="alert">{{ error }}</p>
    <p v-if="message" class="source__success" role="status">{{ message }}</p>

    <template v-if="fields.length">
      <div class="source__heading">
        Schema <VipBadge tone="neutral" size="sm">{{ fields.length }} fields</VipBadge>
      </div>
      <div class="source__schema">
        <div v-for="field in fields" :key="field.name" class="source__field">
          <span>{{ field.name }}</span
          ><code>{{ field.type }}</code>
        </div>
      </div>
    </template>

    <template v-if="preview?.rows.length">
      <div class="source__heading">
        Live preview
        <VipBadge v-if="preview.maskedFields.length" tone="warning" size="sm">sensitive values masked</VipBadge>
      </div>
      <div class="source__preview">
        <table>
          <thead>
            <tr>
              <th v-for="column in preview.columns" :key="column.name">{{ column.displayName }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in preview.rows" :key="index">
              <td v-for="column in preview.columns" :key="column.name">{{ row[column.name] ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.source {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.source__scope,
.source__metadata {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-4);
  background: var(--vip-surface-2);
  border-radius: var(--vip-radius-md);
  font-size: var(--vip-fs-xs);
}
.source__scope span,
.source__metadata span {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--vip-text-muted);
}
.source__scope strong,
.source__metadata strong {
  color: var(--vip-text-secondary);
}
.source__file-label,
.source__heading {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-secondary);
}
.source__file {
  width: 100%;
  color: var(--vip-text-secondary);
}
.source__state {
  padding: var(--vip-sp-4);
}
.source__error {
  color: var(--vip-danger-text);
  font-size: var(--vip-fs-xs);
}
.source__error button {
  color: inherit;
  text-decoration: underline;
  background: none;
  border: 0;
}
.source__success {
  color: var(--vip-success-text);
  font-size: var(--vip-fs-xs);
}
.source__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.source__paging {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.source__schema {
  max-height: 180px;
  overflow: auto;
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
}
.source__field {
  display: flex;
  justify-content: space-between;
  padding: var(--vip-sp-3) var(--vip-sp-4);
  border-bottom: 1px solid var(--vip-border-subtle);
  font-size: var(--vip-fs-xs);
}
.source__field code {
  color: var(--vip-text-muted);
}
.source__preview {
  overflow: auto;
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
}
.source__preview table {
  border-collapse: collapse;
  font-size: var(--vip-fs-xs);
}
.source__preview th,
.source__preview td {
  padding: var(--vip-sp-3);
  border-right: 1px solid var(--vip-border-subtle);
  white-space: nowrap;
  text-align: left;
}
.source__preview th {
  background: var(--vip-surface-2);
  position: sticky;
  top: 0;
}
</style>
