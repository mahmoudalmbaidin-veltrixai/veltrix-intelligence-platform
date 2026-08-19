<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQuery, useMutation } from '@/shared/lib/query'
import { formatNumber } from '@/shared/lib/format'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import { semanticService } from '@/shared/services/semanticModels'
import { semanticStudioService, type Metric, type MetricFormat } from './semantic.service'
import type { Aggregation } from '@/shared/types/semantic'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipTextarea from '@/shared/ui/VipTextarea.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const platform = usePlatformStore()
const canWrite = computed(() => platform.can('semantic_metric.manage'))

const { data, isLoading, refetch } = useQuery(
  () => 'semantic:metrics',
  () => semanticStudioService.listMetrics(),
)
const { data: models } = useQuery('semantic:metric-models', () => semanticStudioService.listModels())
const { data: definitions } = useQuery('semantic:metric-definitions', async () => {
  const rows = await semanticStudioService.listModels()
  return Promise.all(rows.map((model) => semanticStudioService.getDefinition(model.id)))
})

const columns: Column<Metric>[] = [
  { key: 'name', label: 'Metric' },
  { key: 'measureId', label: 'Measure' },
  { key: 'aggregation', label: 'Aggregation' },
  { key: 'target', label: 'Target', align: 'right' },
  { key: 'status', label: 'Status' },
  { key: 'owner', label: 'Owner' },
]

function measureLabel(measureId: string): string {
  for (const definition of definitions.value ?? []) {
    const measure = definition.measures.find((item) => item.key === measureId)
    if (measure) return measure.name
  }
  return measureId
}
function metricFormat(m: Metric): MetricFormat {
  return m.format
}
function formatTarget(m: Metric): string {
  if (m.target == null) return '—'
  return formatNumber(m.target, { style: metricFormat(m) })
}

const statusTone = (s: Metric['status']) => (s === 'published' ? 'success' : 'warning')

/* ---- create dialog ---- */
const dialogOpen = ref(false)
const measureModels = computed(() => (models.value ?? []).map((m) => ({ value: m.id, label: m.label })))

interface Draft {
  name: string
  description: string
  modelId: string
  measureId: string
  aggregation: Aggregation
  format: MetricFormat
  target: number | null
  warning: number | null
  critical: number | null
}
const draft = reactive<Draft>({
  name: '',
  description: '',
  modelId: '',
  measureId: '',
  aggregation: 'sum',
  format: 'plain',
  target: null,
  warning: null,
  critical: null,
})

const activeDefinition = computed(
  () => (definitions.value ?? []).find((item) => item.model.id === draft.modelId) ?? definitions.value?.[0],
)
const measureOptions = computed(() =>
  (activeDefinition.value?.measures ?? []).map((measure) => ({
    value: measure.key,
    label: measure.name,
  })),
)
const aggOptions = [
  { value: 'sum', label: 'Sum' },
  { value: 'avg', label: 'Average' },
  { value: 'min', label: 'Minimum' },
  { value: 'max', label: 'Maximum' },
  { value: 'count', label: 'Count' },
]
const formatOptions = [
  { value: 'plain', label: 'Plain number' },
  { value: 'currency', label: 'Currency' },
  { value: 'percent', label: 'Percent' },
  { value: 'compact', label: 'Compact' },
]

watch(
  () => draft.modelId,
  () => {
    draft.measureId = measureOptions.value[0]?.value ?? ''
    const measure = activeDefinition.value?.measures.find((item) => item.key === draft.measureId)
    if (measure) {
      draft.aggregation = measure.aggregation as Aggregation
    }
  },
)

function openDialog() {
  draft.name = ''
  draft.description = ''
  draft.modelId = models.value?.[0]?.id ?? ''
  draft.measureId = measureOptions.value[0]?.value ?? ''
  const measure = activeDefinition.value?.measures.find((item) => item.key === draft.measureId)
  draft.aggregation = (measure?.aggregation as Aggregation) ?? 'sum'
  draft.format = 'plain'
  draft.target = null
  draft.warning = null
  draft.critical = null
  dialogOpen.value = true
}

/* ---- live preview ---- */
const previewValue = ref<number | null>(null)
const previewLoading = ref(false)
let previewToken = 0

watch(
  () => [draft.modelId, draft.measureId, draft.aggregation, dialogOpen.value] as const,
  async () => {
    if (!dialogOpen.value || !draft.measureId) {
      previewValue.value = null
      return
    }
    const token = ++previewToken
    previewLoading.value = true
    try {
      const result = await semanticService.query({
        modelId: draft.modelId,
        measures: [{ fieldId: draft.measureId, aggregation: draft.aggregation }],
        dimensions: [],
        filters: [],
      })
      if (token !== previewToken) return
      const row = result.rows[0]
      const v = row ? row[draft.measureId] : null
      previewValue.value = typeof v === 'number' ? v : null
    } catch {
      previewValue.value = null
    } finally {
      if (token === previewToken) previewLoading.value = false
    }
  },
  { immediate: true },
)

const previewFormatted = computed(() =>
  previewValue.value == null ? '—' : formatNumber(previewValue.value, { style: draft.format }),
)

const nameError = computed(() => (draft.name.trim().length === 0 ? 'Name is required' : ''))
const canSubmit = computed(() => !nameError.value && !!draft.measureId)

const { mutate, isPending } = useMutation((input: Omit<Metric, 'id'>) => semanticStudioService.createMetric(input), {
  invalidate: ['semantic:metrics'],
  onSuccess: (m) => {
    ui.pushToast({ kind: 'success', title: 'Metric created', message: `${m.name} added as ${m.status}.` })
    dialogOpen.value = false
    refetch()
  },
})

async function submit() {
  if (!canSubmit.value) return
  await mutate({
    name: draft.name.trim(),
    modelId: draft.modelId,
    description: draft.description.trim(),
    measureId: draft.measureId,
    aggregation: draft.aggregation,
    format: draft.format,
    target: draft.target ?? undefined,
    thresholds:
      draft.warning != null && draft.critical != null
        ? { warning: draft.warning, critical: draft.critical }
        : undefined,
    owner: platform.user.name,
    status: 'draft',
  })
}
</script>

<template>
  <div class="wrap">
    <VipPageHeader
      title="Metrics &amp; KPIs"
      description="Curated, certified measures with targets and alert thresholds — the single source of truth for the business."
    >
      <template #actions>
        <VipButton variant="primary" icon="plus" :disabled="!canWrite" @click="openDialog">New metric</VipButton>
      </template>
    </VipPageHeader>

    <VipCard :padded="false">
      <VipTable
        :columns="columns"
        :rows="data ?? []"
        :row-key="(r) => r.id"
        :loading="isLoading"
        empty-title="No metrics defined"
        empty-description="Create your first KPI to track it across dashboards and reports."
      >
        <template #cell-name="{ row }">
          <div class="c-name">
            <span class="c-name__label">{{ row.name }}</span>
            <span class="c-name__desc">{{ row.description }}</span>
          </div>
        </template>
        <template #cell-measureId="{ row }">
          <VipBadge tone="brand" variant="soft" size="sm">{{ measureLabel(row.measureId) }}</VipBadge>
        </template>
        <template #cell-aggregation="{ value }">
          <span class="mono">{{ value }}</span>
        </template>
        <template #cell-target="{ row }">{{ formatTarget(row) }}</template>
        <template #cell-status="{ row }">
          <VipBadge :tone="statusTone(row.status)" variant="soft" size="sm">{{ row.status }}</VipBadge>
        </template>
      </VipTable>
    </VipCard>

    <VipDialog
      :open="dialogOpen"
      title="New metric"
      description="Define a governed KPI backed by a semantic measure."
      size="lg"
      @close="dialogOpen = false"
    >
      <div class="builder">
        <div class="builder__form">
          <VipInput
            v-model="draft.name"
            label="Name"
            placeholder="e.g. Net Revenue"
            required
            :error="draft.name ? nameError : ''"
          />
          <VipTextarea
            v-model="draft.description"
            label="Description"
            :rows="2"
            placeholder="What does this metric represent?"
          />
          <div class="row2">
            <VipSelect v-model="draft.modelId" :options="measureModels" label="Model" />
            <VipSelect
              v-model="draft.measureId"
              :options="measureOptions"
              label="Measure"
              placeholder="Select a measure"
            />
          </div>
          <div class="row2">
            <VipSelect v-model="draft.aggregation" :options="aggOptions" label="Aggregation" />
            <VipSelect v-model="draft.format" :options="formatOptions" label="Format" />
          </div>
          <VipInput v-model.number="draft.target" type="number" label="Target" placeholder="Optional target value" />
          <div class="row2">
            <VipInput v-model.number="draft.warning" type="number" label="Warning threshold" placeholder="Optional" />
            <VipInput v-model.number="draft.critical" type="number" label="Critical threshold" placeholder="Optional" />
          </div>
        </div>
        <aside class="builder__preview">
          <div class="preview__label">Live preview</div>
          <div class="preview__value">
            <VipSpinner v-if="previewLoading" :size="18" />
            <template v-else>{{ previewFormatted }}</template>
          </div>
          <div class="preview__meta">{{ measureLabel(draft.measureId) || 'No measure' }} · {{ draft.aggregation }}</div>
          <div v-if="draft.target != null" class="preview__target">
            Target {{ formatNumber(draft.target, { style: draft.format }) }}
          </div>
          <div class="preview__note">Live value from the governed semantic query engine.</div>
        </aside>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="dialogOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="isPending" :disabled="!canSubmit" @click="submit"
          >Create metric</VipButton
        >
      </template>
    </VipDialog>
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
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mono {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
}

.builder {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: var(--vip-sp-7);
}
.builder__form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-5);
}
.builder__preview {
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-lg);
  padding: var(--vip-sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
  height: fit-content;
}
.preview__label {
  font-size: var(--vip-fs-2xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
}
.preview__value {
  font-size: var(--vip-fs-3xl);
  font-weight: var(--vip-fw-bold);
  color: var(--vip-text-primary);
  min-height: 34px;
  display: flex;
  align-items: center;
}
.preview__meta {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-secondary);
}
.preview__target {
  font-size: var(--vip-fs-xs);
  color: var(--vip-brand-text);
}
.preview__note {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-disabled);
  margin-top: var(--vip-sp-3);
  padding-top: var(--vip-sp-4);
  border-top: 1px solid var(--vip-border-subtle);
}
</style>
