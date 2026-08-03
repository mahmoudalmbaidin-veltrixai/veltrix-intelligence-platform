<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import {
  semanticStudioService,
  type DimensionInput,
  type MeasureInput,
  type SemanticModelVersion,
  type SemanticValidation,
  type StudioDimension,
  type StudioMeasure,
} from './semantic.service'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'
import VipTextarea from '@/shared/ui/VipTextarea.vue'
import ResourceShareButton from '@/modules/access/ResourceShareButton.vue'
import { mapResourceAccess, resourceCan } from '@/shared/lib/resourceAccess'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const platform = usePlatformStore()
const modelId = computed(() => String(route.params.id))
// Resource-aware capabilities from the backend effective-access decision
// (authoritative). Edit/publish map to the model's edit/manage levels; sharing to
// the manage-access authority. Fall back to broad permissions until access loads.
const effectiveAccess = computed(() => mapResourceAccess(definition.value?.model.access))
const canEdit = computed(() =>
  effectiveAccess.value ? resourceCan(effectiveAccess.value, 'edit') : platform.can('semantic_model.update'),
)
const canPublish = computed(() =>
  effectiveAccess.value ? resourceCan(effectiveAccess.value, 'manage') : platform.can('semantic_model.publish'),
)
const canArchive = computed(() =>
  effectiveAccess.value ? resourceCan(effectiveAccess.value, 'manage') : platform.can('semantic_model.archive'),
)
const canManageAccess = computed(() => effectiveAccess.value?.canManageAccess ?? false)

const {
  data: definition,
  isLoading,
  error,
  refetch,
} = useQuery(
  () => `semantic:definition:${modelId.value}`,
  () => semanticStudioService.getDefinition(modelId.value),
)
const tab = ref<'dimensions' | 'measures' | 'metrics' | 'kpis' | 'settings' | 'history'>('dimensions')
const { data: versions, refetch: refetchVersions } = useQuery(
  () => `semantic:versions:${modelId.value}`,
  () => semanticStudioService.listVersions(modelId.value),
)
const selectedVersionId = ref('')
const selectedVersion = computed<SemanticModelVersion | null>(
  () => versions.value?.find((item) => item.id === selectedVersionId.value) ?? versions.value?.[0] ?? null,
)
watch(
  versions,
  (value) => {
    if (!value?.some((item) => item.id === selectedVersionId.value)) {
      selectedVersionId.value = value?.[0]?.id ?? ''
    }
  },
  { immediate: true },
)
const tabs = computed(() => [
  { value: 'dimensions', label: 'Dimensions', count: definition.value?.dimensions.length ?? 0 },
  { value: 'measures', label: 'Measures', count: definition.value?.measures.length ?? 0 },
  { value: 'metrics', label: 'Metrics', count: definition.value?.metrics.length ?? 0 },
  { value: 'kpis', label: 'KPIs', count: definition.value?.kpis.length ?? 0 },
  { value: 'settings', label: 'Settings' },
  { value: 'history', label: 'Versions' },
])
// Editing a published model is allowed: the first edit opens the next draft
// version server-side (the published version stays immutable), then Publish mints
// that next sequential version. The view refetches after every edit so status and
// version reflect the re-draft.
const isEditable = computed(() => canEdit.value)

const settings = reactive({ name: '', description: '', timezone: 'UTC', currency: 'USD', version: 1 })
const savedSettings = ref('')
watch(
  definition,
  (value) => {
    if (!value) return
    Object.assign(settings, {
      name: value.model.name,
      description: value.model.description,
      timezone: value.model.timezone,
      currency: value.model.currency,
      version: value.model.version,
    })
    savedSettings.value = JSON.stringify(settings)
  },
  { immediate: true },
)
const dirty = computed(() => !!definition.value && JSON.stringify(settings) !== savedSettings.value)
function warnBeforeUnload(event: BeforeUnloadEvent): void {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}
onMounted(() => window.addEventListener('beforeunload', warnBeforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', warnBeforeUnload))
onBeforeRouteLeave(() => !dirty.value || window.confirm('Discard unsaved semantic model changes?'))

const saving = ref(false)
const publishing = ref(false)
const validation = ref<SemanticValidation | null>(null)
async function saveSettings(): Promise<void> {
  if (!definition.value || !isEditable.value) return
  saving.value = true
  try {
    await semanticStudioService.updateModel(modelId.value, {
      name: settings.name.trim(),
      description: settings.description.trim(),
      timezone: settings.timezone.trim(),
      currency: settings.currency.toUpperCase(),
      version: settings.version,
    })
    await Promise.all([refetch(), refetchVersions()])
    ui.pushToast({ kind: 'success', title: 'Draft saved', message: settings.name })
  } catch (cause) {
    ui.pushToast({ kind: 'error', title: 'Save failed', message: (cause as Error).message })
  } finally {
    saving.value = false
  }
}
async function validate(): Promise<SemanticValidation | null> {
  try {
    validation.value = await semanticStudioService.validateModel(modelId.value)
    return validation.value
  } catch (cause) {
    ui.pushToast({ kind: 'error', title: 'Validation failed', message: (cause as Error).message })
    return null
  }
}
async function publish(): Promise<void> {
  if (!canPublish.value || definition.value?.model.status !== 'draft') return
  if (dirty.value) await saveSettings()
  publishing.value = true
  try {
    const result = await validate()
    if (!result?.valid) return
    await semanticStudioService.publishModel(modelId.value)
    await Promise.all([refetch(), refetchVersions()])
    ui.pushToast({ kind: 'success', title: 'Model published', message: settings.name })
  } catch (cause) {
    ui.pushToast({ kind: 'error', title: 'Publish failed', message: (cause as Error).message })
  } finally {
    publishing.value = false
  }
}
async function archive(): Promise<void> {
  if (!canArchive.value || !window.confirm(`Archive ${settings.name}?`)) return
  try {
    await semanticStudioService.archiveModel(modelId.value)
    ui.pushToast({ kind: 'success', title: 'Model archived', message: settings.name })
    await router.push('/semantic')
  } catch (cause) {
    ui.pushToast({ kind: 'error', title: 'Archive failed', message: (cause as Error).message })
  }
}

type EditorKind = 'dimension' | 'measure'
const editorOpen = ref(false)
const editorKind = ref<EditorKind>('dimension')
const editingId = ref<string | null>(null)
const editorError = ref('')
const editorBusy = ref(false)
const editor = reactive({
  name: '',
  key: '',
  description: '',
  fieldId: '',
  dimensionType: 'categorical',
  aggregation: 'sum',
  isTime: false,
  granularities: 'day,month,quarter,year',
  hidden: false,
})
const fieldOptions = computed(() =>
  (definition.value?.fields ?? []).map((field) => ({
    value: field.id,
    label: `${field.display_name || field.source_name} · ${field.physical_data_type}`,
  })),
)
const dimensionTypeOptions = [
  { value: 'categorical', label: 'Categorical' },
  { value: 'time', label: 'Time' },
  { value: 'geographic', label: 'Geographic' },
  { value: 'identifier', label: 'Identifier' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'numeric', label: 'Numeric' },
]
const aggregationOptions = [
  { value: 'sum', label: 'Sum' },
  { value: 'count', label: 'Count' },
  { value: 'count_distinct', label: 'Count distinct' },
  { value: 'average', label: 'Average' },
  { value: 'min', label: 'Minimum' },
  { value: 'max', label: 'Maximum' },
]
function keyFor(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}
function openEditor(kind: EditorKind, item?: StudioDimension | StudioMeasure): void {
  if (!isEditable.value) return
  editorKind.value = kind
  editingId.value = item?.id ?? null
  editor.name = item?.name ?? ''
  editor.key = item?.key ?? ''
  editor.description = item?.description ?? ''
  editor.fieldId = item?.field_id ?? fieldOptions.value[0]?.value ?? ''
  editor.hidden = item?.is_hidden ?? false
  editor.dimensionType = 'dimension_type' in (item ?? {}) ? (item as StudioDimension).dimension_type : 'categorical'
  editor.isTime = 'is_time_dimension' in (item ?? {}) && (item as StudioDimension).is_time_dimension
  editor.granularities =
    'time_granularities' in (item ?? {}) ? (item as StudioDimension).time_granularities.join(',') : ''
  editor.aggregation = 'aggregation' in (item ?? {}) ? (item as StudioMeasure).aggregation : 'sum'
  editorError.value = ''
  editorOpen.value = true
}
async function saveEditor(): Promise<void> {
  if (!isEditable.value) return
  const model = definition.value?.model
  editor.key ||= keyFor(editor.name)
  if (!model || !editor.name.trim() || !/^[a-z][a-z0-9_]{1,99}$/.test(editor.key)) {
    editorError.value = 'Name and a valid stable key are required.'
    return
  }
  if (editorKind.value === 'dimension' && !editor.fieldId) {
    editorError.value = 'Select a dataset field.'
    return
  }
  editorBusy.value = true
  try {
    if (editorKind.value === 'dimension') {
      const payload: DimensionInput = {
        dataset_id: model.primary_dataset_id,
        field_id: editor.fieldId,
        key: editor.key,
        name: editor.name.trim(),
        description: editor.description.trim(),
        dimension_type: editor.dimensionType,
        is_time_dimension: editor.isTime,
        time_granularities: editor.isTime
          ? editor.granularities
              .split(',')
              .map((item) => item.trim())
              .filter(Boolean)
          : [],
        is_hidden: editor.hidden,
      }
      if (editingId.value) await semanticStudioService.updateDimension(modelId.value, editingId.value, payload)
      else await semanticStudioService.createDimension(modelId.value, payload)
    } else {
      const payload: MeasureInput = {
        dataset_id: model.primary_dataset_id,
        field_id: editor.aggregation === 'count' ? null : editor.fieldId,
        key: editor.key,
        name: editor.name.trim(),
        description: editor.description.trim(),
        aggregation: editor.aggregation,
        is_hidden: editor.hidden,
      }
      if (editingId.value) await semanticStudioService.updateMeasure(modelId.value, editingId.value, payload)
      else await semanticStudioService.createMeasure(modelId.value, payload)
    }
    editorOpen.value = false
    await refetch()
    ui.pushToast({ kind: 'success', title: `${editorKind.value} saved`, message: editor.name })
  } catch (cause) {
    editorError.value = (cause as Error).message
  } finally {
    editorBusy.value = false
  }
}
async function remove(kind: EditorKind, id: string, name: string): Promise<void> {
  if (!isEditable.value) return
  if (!window.confirm(`Delete ${name}? This cannot be undone.`)) return
  try {
    if (kind === 'dimension') await semanticStudioService.deleteDimension(modelId.value, id)
    else await semanticStudioService.deleteMeasure(modelId.value, id)
    await refetch()
  } catch (cause) {
    ui.pushToast({ kind: 'error', title: 'Delete failed', message: (cause as Error).message })
  }
}
</script>

<template>
  <div class="semantic-builder">
    <VipPageHeader :title="definition?.model.name ?? 'Semantic model'" :description="definition?.model.description">
      <template #status>
        <VipBadge :tone="definition?.model.status === 'published' ? 'success' : 'warning'" variant="soft">
          {{ definition?.model.status ?? 'draft' }}
        </VipBadge>
        <VipBadge v-if="dirty" tone="warning" variant="outline">Unsaved changes</VipBadge>
      </template>
      <template #actions>
        <VipButton variant="tertiary" :disabled="!canArchive" @click="archive">Archive</VipButton>
        <VipButton variant="secondary" :disabled="!isEditable || !dirty" :loading="saving" @click="saveSettings">
          Save draft
        </VipButton>
        <VipButton variant="secondary" @click="validate">Validate</VipButton>
        <VipButton
          variant="primary"
          :disabled="!canPublish || definition?.model.status !== 'draft'"
          :loading="publishing"
          @click="publish"
        >
          Publish
        </VipButton>
        <ResourceShareButton
          v-if="definition?.model.id && canManageAccess"
          resource-type="semantic_model"
          :resource-id="definition.model.id"
          :resource-name="definition.model.name"
          variant="secondary"
        />
      </template>
      <template #tabs><VipTabs v-model="tab" :tabs="tabs" /></template>
    </VipPageHeader>

    <div v-if="isLoading" class="state"><VipSpinner /> Loading semantic definition…</div>
    <VipAlert v-else-if="error" tone="danger" title="Semantic model unavailable">{{ error.message }}</VipAlert>
    <template v-else-if="definition">
      <VipAlert v-if="validation && !validation.valid" tone="danger" title="Validation failed">
        <ul>
          <li v-for="issue in validation.errors" :key="issue.code + issue.resource">{{ issue.message }}</li>
        </ul>
      </VipAlert>
      <VipAlert v-else-if="validation?.valid" tone="success" title="Validation passed">
        The semantic model is structurally valid.
      </VipAlert>

      <section v-if="tab === 'dimensions' || tab === 'measures'" class="collection">
        <div class="collection__head">
          <div>
            <h2>{{ tab === 'dimensions' ? 'Dimensions' : 'Measures' }}</h2>
            <p>Definitions are persisted directly to the governed semantic layer.</p>
          </div>
          <VipButton
            variant="primary"
            icon="plus"
            :disabled="!isEditable"
            @click="openEditor(tab === 'dimensions' ? 'dimension' : 'measure')"
          >
            Add {{ tab === 'dimensions' ? 'dimension' : 'measure' }}
          </VipButton>
        </div>
        <VipEmptyState
          v-if="!(tab === 'dimensions' ? definition.dimensions : definition.measures).length"
          icon="layers"
          :title="`No ${tab} defined`"
          description="Add the first governed definition to continue."
        />
        <div v-else class="cards">
          <VipCard v-for="item in tab === 'dimensions' ? definition.dimensions : definition.measures" :key="item.id">
            <div class="item-head">
              <div>
                <h3>{{ item.name }}</h3>
                <code>{{ item.key }}</code>
              </div>
              <VipBadge tone="neutral" variant="soft">
                {{ 'aggregation' in item ? item.aggregation : item.dimension_type }}
              </VipBadge>
            </div>
            <p>{{ item.description || 'No description provided.' }}</p>
            <div class="item-actions">
              <VipButton
                variant="tertiary"
                size="sm"
                :disabled="!isEditable"
                @click="openEditor(tab === 'dimensions' ? 'dimension' : 'measure', item)"
                >Edit</VipButton
              >
              <VipButton
                variant="tertiary"
                size="sm"
                :disabled="!isEditable"
                @click="remove(tab === 'dimensions' ? 'dimension' : 'measure', item.id, item.name)"
                >Delete</VipButton
              >
            </div>
          </VipCard>
        </div>
      </section>

      <section v-else-if="tab === 'metrics' || tab === 'kpis'" class="collection">
        <div class="collection__head">
          <div>
            <h2>{{ tab === 'metrics' ? 'Metrics' : 'KPIs' }}</h2>
            <p>Manage these definitions in the dedicated Metrics &amp; KPIs workspace.</p>
          </div>
          <VipButton variant="primary" @click="router.push('/semantic/metrics')">Open metrics workspace</VipButton>
        </div>
        <div class="cards">
          <VipCard v-for="item in tab === 'metrics' ? definition.metrics : definition.kpis" :key="item.id">
            <div class="item-head">
              <h3>{{ item.name }}</h3>
              <VipBadge variant="soft">{{ item.status }}</VipBadge>
            </div>
            <p>{{ item.description || 'No description provided.' }}</p>
          </VipCard>
        </div>
      </section>

      <section v-else-if="tab === 'settings'" class="settings">
        <VipCard>
          <div class="form">
            <VipInput v-model="settings.name" label="Model name" required :disabled="!isEditable" />
            <VipTextarea v-model="settings.description" label="Description" :disabled="!isEditable" />
            <div class="form-row">
              <VipInput v-model="settings.timezone" label="Timezone" required :disabled="!isEditable" />
              <VipInput v-model="settings.currency" label="Currency" maxlength="3" required :disabled="!isEditable" />
            </div>
          </div>
        </VipCard>
      </section>

      <section v-else class="history">
        <VipCard>
          <h2>Version history</h2>
          <VipEmptyState
            v-if="!versions?.length"
            icon="clock"
            title="No published versions"
            description="Publish this model to create its first immutable version."
          />
          <template v-else>
            <VipSelect
              v-model="selectedVersionId"
              label="Published version"
              :options="
                versions.map((item) => ({
                  value: item.id,
                  label: `Version ${item.version_number} · ${new Date(item.published_at).toLocaleString()}`,
                }))
              "
            />
            <div v-if="selectedVersion" class="version">
              <div>
                <strong>Version {{ selectedVersion.version_number }}</strong>
                <p>Immutable publication · {{ new Date(selectedVersion.published_at).toLocaleString() }}</p>
                <p>
                  {{ selectedVersion.definition.dimensions?.length ?? 0 }} dimensions ·
                  {{ selectedVersion.definition.measures?.length ?? 0 }} measures ·
                  {{ selectedVersion.definition.metrics?.length ?? 0 }} metrics ·
                  {{ selectedVersion.definition.kpis?.length ?? 0 }} KPIs
                </p>
              </div>
              <VipBadge tone="success">Published</VipBadge>
            </div>
          </template>
        </VipCard>
      </section>
    </template>

    <VipDialog
      :open="editorOpen"
      :title="`${editingId ? 'Edit' : 'Add'} ${editorKind}`"
      description="Bind this definition to a real field in the primary dataset."
      @close="editorOpen = false"
    >
      <div class="form">
        <VipInput v-model="editor.name" label="Name" required @blur="editor.key ||= keyFor(editor.name)" />
        <VipInput v-model="editor.key" label="Stable key" required />
        <VipSelect v-model="editor.fieldId" :options="fieldOptions" label="Dataset field" required />
        <VipTextarea v-model="editor.description" label="Description" />
        <VipSelect
          v-if="editorKind === 'dimension'"
          v-model="editor.dimensionType"
          :options="dimensionTypeOptions"
          label="Dimension type"
        />
        <VipSelect v-else v-model="editor.aggregation" :options="aggregationOptions" label="Aggregation" />
        <div v-if="editorKind === 'dimension'" class="switch-row">
          <span>Time dimension</span><VipSwitch v-model="editor.isTime" />
        </div>
        <VipInput
          v-if="editorKind === 'dimension' && editor.isTime"
          v-model="editor.granularities"
          label="Granularities"
          help="Comma-separated: day, week, month, quarter, year"
        />
        <div class="switch-row"><span>Hidden from consumers</span><VipSwitch v-model="editor.hidden" /></div>
        <p v-if="editorError" class="form-error" role="alert">{{ editorError }}</p>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="editorOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :disabled="!isEditable" :loading="editorBusy" @click="saveEditor">Save</VipButton>
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.semantic-builder {
  max-width: 1280px;
}
.state {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-9);
  color: var(--vip-text-muted);
}
.collection,
.settings,
.history {
  margin-top: var(--vip-sp-6);
}
.collection__head {
  display: flex;
  justify-content: space-between;
  gap: var(--vip-sp-6);
  align-items: center;
  margin-bottom: var(--vip-sp-6);
}
.collection__head h2,
.history h2 {
  font-size: var(--vip-fs-xl);
  color: var(--vip-text-primary);
}
.collection__head p,
.version p {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  margin-top: var(--vip-sp-2);
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--vip-sp-5);
}
.item-head,
.item-actions,
.version {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--vip-sp-4);
}
.item-head h3 {
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
}
.item-head code {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-xs);
}
.cards p {
  color: var(--vip-text-secondary);
  margin-top: var(--vip-sp-4);
  min-height: 2.5em;
}
.item-actions {
  justify-content: flex-end;
  margin-top: var(--vip-sp-5);
  border-top: 1px solid var(--vip-border-subtle);
  padding-top: var(--vip-sp-3);
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 140px;
  gap: var(--vip-sp-4);
}
.switch-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--vip-text-secondary);
}
.form-error {
  color: var(--vip-danger-text);
  font-size: var(--vip-fs-sm);
}
.version {
  margin-top: var(--vip-sp-5);
}
@media (max-width: 720px) {
  .collection__head,
  .version {
    align-items: stretch;
    flex-direction: column;
  }
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
