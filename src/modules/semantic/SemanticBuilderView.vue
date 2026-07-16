<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { relativeTime } from '@/shared/lib/format'
import { isoAgo } from '@/shared/lib/mock'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import { MODELS } from '@/shared/services/semanticModels'
import { semanticStudioService } from './semantic.service'
import type { Aggregation, DataType, SemanticField } from '@/shared/types/semantic'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const route = useRoute()
const ui = useUiStore()
const platform = usePlatformStore()
const canWrite = computed(() => platform.can('semantic:write'))

const modelId = computed(() => String(route.params.id ?? MODELS[0].id))
const { data: model, isLoading } = useQuery(
  () => `semantic:model:${modelId.value}`,
  async () => (await semanticStudioService.getModel(modelId.value)) ?? MODELS[0],
)

type TabKey = 'entities' | 'relationships' | 'dimensions' | 'measures' | 'metrics' | 'history'
const tab = ref<TabKey>('entities')
const tabs = computed(() => {
  const f = model.value?.fields ?? []
  return [
    { value: 'entities', label: 'Entities', count: model.value?.entities.length },
    { value: 'relationships', label: 'Relationships', count: hierarchies.value.length },
    { value: 'dimensions', label: 'Dimensions', count: f.filter((x) => x.role === 'dimension' || x.role === 'time').length },
    { value: 'measures', label: 'Measures', count: f.filter((x) => x.role === 'measure').length },
    { value: 'metrics', label: 'Metrics', count: f.filter((x) => x.role === 'metric').length },
    { value: 'history', label: 'Version history' },
  ]
})

/* ---- selection + per-field local config overrides ---- */
const selectedId = ref<string | null>(null)
const selected = computed(() => model.value?.fields.find((f) => f.id === selectedId.value) ?? null)

interface FieldConfig { label: string; role: SemanticField['role']; aggregation: Aggregation; format: string; visible: boolean }
const overrides = reactive<Record<string, FieldConfig>>({})

function configFor(f: SemanticField): FieldConfig {
  if (!overrides[f.id]) {
    overrides[f.id] = {
      label: f.label,
      role: f.role,
      aggregation: f.defaultAggregation ?? (f.role === 'measure' || f.role === 'metric' ? 'sum' : 'none'),
      format: f.format?.style ?? 'plain',
      visible: true,
    }
  }
  return overrides[f.id]
}

watch(model, (m) => {
  if (m && !selectedId.value) selectedId.value = m.fields[0]?.id ?? null
})

function selectField(f: SemanticField) {
  selectedId.value = f.id
  configFor(f)
}

/* ---- derived groupings ---- */
const dimensions = computed(() => (model.value?.fields ?? []).filter((f) => f.role === 'dimension' || f.role === 'time'))
const measures = computed(() => (model.value?.fields ?? []).filter((f) => f.role === 'measure'))
const metrics = computed(() => (model.value?.fields ?? []).filter((f) => f.role === 'metric'))

interface Hierarchy { id: string; label: string; levels: SemanticField[] }
const hierarchies = computed<Hierarchy[]>(() => {
  const map = new Map<string, SemanticField[]>()
  for (const f of model.value?.fields ?? []) {
    if (!f.hierarchyId) continue
    const arr = map.get(f.hierarchyId) ?? []
    arr.push(f)
    map.set(f.hierarchyId, arr)
  }
  return [...map.entries()].map(([id, levels]) => ({
    id,
    label: levels[0]?.folder ?? id,
    levels: [...levels].sort((a, b) => (a.hierarchyLevel ?? 0) - (b.hierarchyLevel ?? 0)),
  }))
})

const aggOptions = [
  { value: 'sum', label: 'Sum' }, { value: 'avg', label: 'Average' },
  { value: 'min', label: 'Minimum' }, { value: 'max', label: 'Maximum' },
  { value: 'count', label: 'Count' }, { value: 'count_distinct', label: 'Count distinct' },
  { value: 'median', label: 'Median' }, { value: 'none', label: 'None' },
]
const formatOptions = [
  { value: 'plain', label: 'Plain number' }, { value: 'currency', label: 'Currency' },
  { value: 'percent', label: 'Percent' }, { value: 'compact', label: 'Compact' },
]
const roleOptions = [
  { value: 'dimension', label: 'Dimension' }, { value: 'measure', label: 'Measure' },
  { value: 'metric', label: 'Metric' }, { value: 'time', label: 'Time' },
]

const TYPE_ICON: Record<DataType, string> = {
  string: 'text', number: 'hash', integer: 'hash', currency: 'card',
  percent: 'pieChart', boolean: 'check', date: 'calendar', datetime: 'calendarClock', geo: 'target',
}
const ROLE_TONE: Record<SemanticField['role'], 'brand' | 'info' | 'success' | 'warning'> = {
  dimension: 'info', measure: 'brand', metric: 'success', time: 'warning',
}

/* ---- publish / validation ---- */
const status = ref<'draft' | 'published'>('published')
const validationIssues = computed(() => {
  const issues: string[] = []
  const noAgg = measures.value.filter((f) => !(f.defaultAggregation || overrides[f.id]?.aggregation) || overrides[f.id]?.aggregation === 'none')
  if (noAgg.length) issues.push(`${noAgg.length} measure(s) have no default aggregation`)
  const noDesc = (model.value?.fields ?? []).filter((f) => !f.description).length
  if (noDesc > 0) issues.push(`${noDesc} field(s) missing a description`)
  return issues
})

function saveDraft() {
  status.value = 'draft'
  ui.pushToast({ kind: 'success', title: 'Draft saved', message: `${model.value?.label} saved as draft.` })
}
function publish() {
  if (validationIssues.value.length) {
    ui.pushToast({ kind: 'warning', title: 'Resolve validation issues', message: validationIssues.value[0] })
    return
  }
  status.value = 'published'
  ui.pushToast({ kind: 'success', title: 'Model published', message: `${model.value?.label} is now certified and query-ready.` })
}

interface Version { id: string; label: string; author: string; when: string; note: string; current?: boolean }
const versions = computed<Version[]>(() => [
  { id: 'v14', label: 'v1.4', author: platform.user.name, when: isoAgo(90), note: 'Added margin metric and KPI folder.', current: true },
  { id: 'v13', label: 'v1.3', author: 'A. Rahman', when: isoAgo(60 * 26), note: 'Renamed Sales Channel dimension.' },
  { id: 'v12', label: 'v1.2', author: 'L. Haddad', when: isoAgo(60 * 24 * 6), note: 'Introduced geography hierarchy.' },
  { id: 'v11', label: 'v1.1', author: 'A. Rahman', when: isoAgo(60 * 24 * 18), note: 'Certified for production use.' },
  { id: 'v10', label: 'v1.0', author: 'A. Rahman', when: isoAgo(60 * 24 * 40), note: 'Initial model published.' },
])
</script>

<template>
  <div class="wrap">
    <VipPageHeader :title="model?.label ?? 'Semantic model'" :description="model?.description">
      <template #status>
        <VipBadge :tone="status === 'published' ? 'success' : 'warning'" variant="soft">
          {{ status === 'published' ? 'Published' : 'Draft' }}
        </VipBadge>
        <VipBadge v-if="model?.certified" tone="brand" variant="outline" size="sm">
          <VipIcon name="shield" :size="11" /> Certified
        </VipBadge>
      </template>
      <template #actions>
        <VipButton variant="secondary" icon="save" :disabled="!canWrite" @click="saveDraft">Save draft</VipButton>
        <VipButton variant="primary" icon="check" :disabled="!canWrite" @click="publish">Publish</VipButton>
      </template>
      <template #tabs>
        <VipTabs v-model="tab" :tabs="tabs" />
      </template>
    </VipPageHeader>

    <VipAlert v-if="validationIssues.length" tone="warning" title="Validation">
      <ul class="issues">
        <li v-for="(i, n) in validationIssues" :key="n">{{ i }}</li>
      </ul>
    </VipAlert>

    <div v-if="isLoading" class="loading"><VipSpinner /> <span>Loading model…</span></div>

    <div v-else class="builder">
      <!-- LEFT: datasets / entities -->
      <aside class="panel panel--left">
        <div class="panel__head">Datasets &amp; entities</div>
        <div class="panel__body">
          <button
            v-for="e in model?.entities"
            :key="e.id"
            type="button"
            class="entity-row"
          >
            <VipIcon name="database" :size="14" />
            <span class="entity-row__label">{{ e.label }}</span>
            <span class="entity-row__count">{{ e.fields.length }}</span>
          </button>
          <div class="panel__sub">Field folders</div>
          <button
            v-for="folder in [...new Set((model?.fields ?? []).map((f) => f.folder ?? 'General'))]"
            :key="folder"
            type="button"
            class="entity-row entity-row--sub"
          >
            <VipIcon name="folder" :size="14" />
            <span class="entity-row__label">{{ folder }}</span>
          </button>
        </div>
      </aside>

      <!-- CENTER: canvas / tab content -->
      <section class="panel panel--center">
        <!-- Entities canvas -->
        <div v-if="tab === 'entities'" class="canvas">
          <VipCard v-for="e in model?.entities" :key="e.id" class="entity-card" :padded="false">
            <header class="entity-card__head">
              <span class="entity-card__icon"><VipIcon name="database" :size="16" /></span>
              <div>
                <div class="entity-card__title">{{ e.label }}</div>
                <div class="entity-card__sub">{{ e.fields.length }} fields</div>
              </div>
            </header>
            <ul class="field-list">
              <li
                v-for="f in e.fields"
                :key="f.id"
                class="field"
                :class="{ 'is-selected': f.id === selectedId }"
                @click="selectField(f)"
              >
                <VipIcon :name="TYPE_ICON[f.dataType]" :size="14" class="field__type" />
                <span class="field__label">{{ configFor(f).label }}</span>
                <VipBadge :tone="ROLE_TONE[f.role]" variant="dot" size="sm">{{ f.role }}</VipBadge>
              </li>
            </ul>
          </VipCard>
        </div>

        <!-- Relationships -->
        <div v-else-if="tab === 'relationships'" class="rel">
          <VipEmptyState
            v-if="!hierarchies.length"
            icon="lineage"
            title="No relationships defined"
            description="This model exposes a single flat entity with no drill hierarchies."
          />
          <VipCard v-for="h in hierarchies" v-else :key="h.id" class="rel-card">
            <div class="rel-card__title"><VipIcon name="lineage" :size="15" /> {{ h.label }} hierarchy</div>
            <div class="rel-chain">
              <template v-for="(lvl, i) in h.levels" :key="lvl.id">
                <span class="rel-node">{{ lvl.label }}</span>
                <VipIcon v-if="i < h.levels.length - 1" name="chevronRight" :size="14" class="rel-arrow" />
              </template>
            </div>
          </VipCard>
        </div>

        <!-- Dimensions / Measures / Metrics tables -->
        <div v-else-if="tab === 'dimensions' || tab === 'measures' || tab === 'metrics'" class="list">
          <div
            v-for="f in (tab === 'dimensions' ? dimensions : tab === 'measures' ? measures : metrics)"
            :key="f.id"
            class="list-row"
            :class="{ 'is-selected': f.id === selectedId }"
            @click="selectField(f)"
          >
            <VipIcon :name="TYPE_ICON[f.dataType]" :size="15" class="list-row__type" />
            <div class="list-row__main">
              <div class="list-row__label">{{ configFor(f).label }}</div>
              <div class="list-row__id">{{ f.id }} · {{ f.dataType }}</div>
            </div>
            <VipBadge v-if="f.folder" tone="neutral" variant="soft" size="sm">{{ f.folder }}</VipBadge>
            <VipBadge :tone="ROLE_TONE[f.role]" variant="soft" size="sm">{{ configFor(f).aggregation }}</VipBadge>
          </div>
        </div>

        <!-- Version history -->
        <div v-else class="history">
          <div v-for="v in versions" :key="v.id" class="ver">
            <span class="ver__dot" :class="{ 'is-current': v.current }" />
            <div class="ver__body">
              <div class="ver__row">
                <span class="ver__label">{{ v.label }}</span>
                <VipBadge v-if="v.current" tone="brand" variant="soft" size="sm">Current</VipBadge>
                <span class="ver__time">{{ relativeTime(v.when) }}</span>
              </div>
              <div class="ver__note">{{ v.note }}</div>
              <div class="ver__author">{{ v.author }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- RIGHT: inspector -->
      <aside class="panel panel--right">
        <div class="panel__head">Field inspector</div>
        <div v-if="selected" class="panel__body inspector">
          <VipInput :model-value="configFor(selected).label" label="Display label" @update:model-value="(v) => (configFor(selected!).label = String(v))" />
          <VipSelect :model-value="configFor(selected).role" :options="roleOptions" label="Role" @update:model-value="(v) => (configFor(selected!).role = v as SemanticField['role'])" />
          <VipSelect
            v-if="configFor(selected).role === 'measure' || configFor(selected).role === 'metric'"
            :model-value="configFor(selected).aggregation"
            :options="aggOptions"
            label="Default aggregation"
            @update:model-value="(v) => (configFor(selected!).aggregation = v as Aggregation)"
          />
          <VipSelect :model-value="configFor(selected).format" :options="formatOptions" label="Number format" @update:model-value="(v) => (configFor(selected!).format = v)" />
          <div class="inspector__meta">
            <span class="inspector__key">Field id</span>
            <code>{{ selected.id }}</code>
          </div>
          <div class="inspector__meta">
            <span class="inspector__key">Data type</span>
            <VipBadge tone="neutral" variant="soft" size="sm">{{ selected.dataType }}</VipBadge>
          </div>
          <div class="inspector__switch">
            <div>
              <div class="inspector__switch-label">Visible in explore</div>
              <div class="inspector__switch-help">Hide internal or deprecated fields from consumers.</div>
            </div>
            <VipSwitch :model-value="configFor(selected).visible" @update:model-value="(v) => (configFor(selected!).visible = v)" />
          </div>
        </div>
        <div v-else class="panel__body">
          <VipEmptyState icon="target" title="No field selected" description="Select a field from the canvas to configure it." />
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 1360px; }
.issues { margin: 0; padding-left: var(--vip-sp-6); display: flex; flex-direction: column; gap: 2px; }
.loading { display: flex; align-items: center; gap: var(--vip-sp-4); color: var(--vip-text-muted); padding: var(--vip-sp-9); }

.builder {
  display: grid;
  grid-template-columns: 220px 1fr 300px;
  gap: var(--vip-sp-6);
  margin-top: var(--vip-sp-6);
  align-items: start;
}
.panel {
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-lg);
  overflow: hidden;
}
.panel__head {
  padding: var(--vip-sp-4) var(--vip-sp-6);
  font-size: var(--vip-fs-xs);
  font-weight: var(--vip-fw-semibold);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.panel__body { padding: var(--vip-sp-5); }
.panel__sub { font-size: var(--vip-fs-2xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-disabled); margin: var(--vip-sp-6) 0 var(--vip-sp-3); }

.entity-row {
  display: flex; align-items: center; gap: var(--vip-sp-4); width: 100%;
  padding: var(--vip-sp-4) var(--vip-sp-4);
  background: none; border: none; border-radius: var(--vip-radius-sm);
  color: var(--vip-text-secondary); font-size: var(--vip-fs-sm); text-align: left;
}
.entity-row:hover { background: var(--vip-surface-hover); color: var(--vip-text-primary); }
.entity-row--sub { color: var(--vip-text-muted); }
.entity-row__label { flex: 1; }
.entity-row__count { font-size: var(--vip-fs-2xs); color: var(--vip-text-muted); background: var(--vip-surface-3); padding: 1px 6px; border-radius: var(--vip-radius-full); }

.canvas { display: flex; flex-wrap: wrap; gap: var(--vip-sp-6); padding: var(--vip-sp-6); }
.entity-card { width: 300px; }
.entity-card__head { display: flex; align-items: center; gap: var(--vip-sp-4); padding: var(--vip-sp-5) var(--vip-sp-6); border-bottom: 1px solid var(--vip-border-subtle); background: var(--vip-surface-2); }
.entity-card__icon { width: 30px; height: 30px; flex: none; display: inline-flex; align-items: center; justify-content: center; background: var(--vip-brand-soft); color: var(--vip-brand-text); border-radius: var(--vip-radius-sm); }
.entity-card__title { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); color: var(--vip-text-primary); }
.entity-card__sub { font-size: var(--vip-fs-2xs); color: var(--vip-text-muted); }
.field-list { list-style: none; margin: 0; padding: var(--vip-sp-2); }
.field { display: flex; align-items: center; gap: var(--vip-sp-4); padding: var(--vip-sp-3) var(--vip-sp-4); border-radius: var(--vip-radius-sm); cursor: pointer; }
.field:hover { background: var(--vip-surface-hover); }
.field.is-selected { background: var(--vip-brand-soft); }
.field__type { color: var(--vip-text-muted); flex: none; }
.field__label { flex: 1; font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }

.rel { display: flex; flex-direction: column; gap: var(--vip-sp-5); padding: var(--vip-sp-6); }
.rel-card__title { display: flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); margin-bottom: var(--vip-sp-5); }
.rel-chain { display: flex; align-items: center; gap: var(--vip-sp-4); flex-wrap: wrap; }
.rel-node { padding: var(--vip-sp-3) var(--vip-sp-5); background: var(--vip-surface-2); border: 1px solid var(--vip-border); border-radius: var(--vip-radius-md); font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }
.rel-arrow { color: var(--vip-text-disabled); }

.list { padding: var(--vip-sp-3); }
.list-row { display: flex; align-items: center; gap: var(--vip-sp-5); padding: var(--vip-sp-4) var(--vip-sp-5); border-radius: var(--vip-radius-md); cursor: pointer; }
.list-row:hover { background: var(--vip-surface-hover); }
.list-row.is-selected { background: var(--vip-brand-soft); }
.list-row__type { color: var(--vip-text-muted); flex: none; }
.list-row__main { flex: 1; min-width: 0; }
.list-row__label { font-size: var(--vip-fs-md); color: var(--vip-text-primary); }
.list-row__id { font-size: var(--vip-fs-2xs); color: var(--vip-text-muted); font-family: var(--vip-font-mono); }

.history { padding: var(--vip-sp-7); }
.ver { display: flex; gap: var(--vip-sp-5); padding-bottom: var(--vip-sp-6); position: relative; }
.ver:not(:last-child)::before { content: ''; position: absolute; left: 4px; top: 14px; bottom: 0; width: 1px; background: var(--vip-border); }
.ver__dot { width: 9px; height: 9px; flex: none; margin-top: 4px; border-radius: 50%; background: var(--vip-border-strong); z-index: 1; }
.ver__dot.is-current { background: var(--vip-brand-500); }
.ver__row { display: flex; align-items: center; gap: var(--vip-sp-4); }
.ver__label { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); color: var(--vip-text-primary); }
.ver__time { font-size: var(--vip-fs-xs); color: var(--vip-text-disabled); margin-left: auto; }
.ver__note { font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); margin-top: 2px; }
.ver__author { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); margin-top: 2px; }

.inspector { display: flex; flex-direction: column; gap: var(--vip-sp-5); }
.inspector__meta { display: flex; align-items: center; justify-content: space-between; gap: var(--vip-sp-4); font-size: var(--vip-fs-sm); }
.inspector__key { color: var(--vip-text-muted); }
.inspector__meta code { font-family: var(--vip-font-mono); font-size: var(--vip-fs-xs); color: var(--vip-text-secondary); }
.inspector__switch { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--vip-sp-5); padding-top: var(--vip-sp-5); border-top: 1px solid var(--vip-border-subtle); }
.inspector__switch-label { font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); font-weight: var(--vip-fw-medium); }
.inspector__switch-help { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); margin-top: 2px; }
</style>
