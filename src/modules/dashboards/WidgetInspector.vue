<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DashboardEditor } from './useDashboardEditor'
import type { DashboardWidget, FieldWells, WellValue, WidgetType } from '@/shared/types/dashboard'
import type { Aggregation, SemanticField } from '@/shared/types/semantic'
import { MODELS } from '@/shared/services/semanticModels'
import { WIDGET_CATALOG } from './widgetFactory'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const props = defineProps<{ editor: DashboardEditor }>()
const tab = ref<'build' | 'format' | 'interactions' | 'general'>('build')

const w = props.editor.selectedWidget
const model = computed(() => MODELS.find((m) => m.id === w.value?.modelId) ?? MODELS[0])

type DimWellKey = 'xAxis' | 'category' | 'legend' | 'series'
interface WellDef { key: DimWellKey | 'values'; label: string; kind: 'dim' | 'measure' }

const wellDefs = computed<WellDef[]>(() => {
  const t = w.value?.type
  if (!t) return []
  if (['bar', 'column', 'stacked-bar', 'line', 'area'].includes(t)) {
    return [
      { key: 'xAxis', label: 'Axis', kind: 'dim' },
      { key: 'values', label: 'Values', kind: 'measure' },
      { key: 'legend', label: 'Legend / Series', kind: 'dim' },
    ]
  }
  if (t === 'pie' || t === 'donut') return [{ key: 'category', label: 'Category', kind: 'dim' }, { key: 'values', label: 'Values', kind: 'measure' }]
  if (t === 'scatter') return [{ key: 'category', label: 'Details', kind: 'dim' }, { key: 'values', label: 'X / Y / Size', kind: 'measure' }]
  if (t === 'table' || t === 'pivot') return [{ key: 'category', label: 'Rows', kind: 'dim' }, { key: 'values', label: 'Values', kind: 'measure' }]
  return [{ key: 'values', label: 'Value', kind: 'measure' }]
})

const dims = computed(() => model.value.fields.filter((f) => f.role === 'dimension' || f.role === 'time'))
const measures = computed(() => model.value.fields.filter((f) => f.role === 'measure' || f.role === 'metric'))

function fieldLabel(id: string): string {
  return model.value.fields.find((f) => f.id === id)?.label ?? id
}
function patchWells(update: Partial<FieldWells>) {
  if (!w.value) return
  props.editor.patchWidget(w.value.id, { wells: { ...w.value.wells, ...update } })
}
function dimValues(key: DimWellKey): string[] {
  return (w.value?.wells[key] as string[] | undefined) ?? []
}
function addDim(key: DimWellKey, fieldId: string) {
  const list = [...dimValues(key), fieldId]
  patchWells({ [key]: Array.from(new Set(list)) } as Partial<FieldWells>)
}
function removeDim(key: DimWellKey, fieldId: string) {
  patchWells({ [key]: dimValues(key).filter((f) => f !== fieldId) } as Partial<FieldWells>)
}
function addMeasure(fieldId: string) {
  const field = measures.value.find((m) => m.id === fieldId)
  const agg = field?.defaultAggregation ?? 'sum'
  const values: WellValue[] = [...(w.value?.wells.values ?? []), { fieldId, aggregation: agg }]
  patchWells({ values })
}
function removeMeasure(fieldId: string) {
  patchWells({ values: (w.value?.wells.values ?? []).filter((v) => v.fieldId !== fieldId) })
}
function setAgg(fieldId: string, agg: Aggregation) {
  patchWells({ values: (w.value?.wells.values ?? []).map((v) => (v.fieldId === fieldId ? { ...v, aggregation: agg } : v)) })
}

function availableDims(key: DimWellKey): SemanticField[] {
  return dims.value.filter((f) => !dimValues(key).includes(f.id))
}
function availableMeasures(): SemanticField[] {
  const used = new Set((w.value?.wells.values ?? []).map((v) => v.fieldId))
  return measures.value.filter((f) => !used.has(f.id))
}

const aggOptions = [
  { value: 'sum', label: 'Sum' }, { value: 'avg', label: 'Average' }, { value: 'min', label: 'Min' },
  { value: 'max', label: 'Max' }, { value: 'count', label: 'Count' }, { value: 'count_distinct', label: 'Distinct count' },
]

/* format + general helpers */
function patchFormat(patch: Partial<DashboardWidget['format']>) {
  if (w.value) props.editor.patchWidget(w.value.id, { format: { ...w.value.format, ...patch } })
}
function patchGeneral(patch: Partial<DashboardWidget['general']>) {
  if (w.value) props.editor.patchWidget(w.value.id, { general: { ...w.value.general, ...patch } })
}
function patchInteractions(patch: Partial<DashboardWidget['interactions']>) {
  if (w.value) props.editor.patchWidget(w.value.id, { interactions: { ...w.value.interactions, ...patch } })
}
function changeType(t: WidgetType) {
  if (w.value) props.editor.patchWidget(w.value.id, { type: t })
}

/* drop field onto well */
function onDropDim(key: DimWellKey, e: DragEvent) {
  const id = e.dataTransfer?.getData('application/vip-field')
  if (id && dims.value.some((f) => f.id === id)) addDim(key, id)
}
function onDropMeasure(e: DragEvent) {
  const id = e.dataTransfer?.getData('application/vip-field')
  if (id && measures.value.some((f) => f.id === id)) addMeasure(id)
}

const vizTypeOptions = WIDGET_CATALOG.filter((c) => c.group !== 'Content' && c.group !== 'Filter').map((c) => ({ value: c.type, label: c.label }))
</script>

<template>
  <aside class="winsp">
    <div v-if="!w" class="winsp__empty">
      <VipEmptyState icon="chart" title="No visual selected" description="Select a widget to configure its data, formatting and interactions." />
    </div>
    <template v-else>
      <div class="winsp__tabs">
        <VipSegmented
          :model-value="tab"
          :options="[
            { value: 'build', label: 'Build' },
            { value: 'format', label: 'Format' },
            { value: 'interactions', label: 'Interact' },
            { value: 'general', label: 'General' },
          ]"
          size="sm"
          @update:model-value="tab = $event as typeof tab"
        />
      </div>

      <div class="winsp__body">
        <!-- BUILD -->
        <template v-if="tab === 'build'">
          <div class="winsp__section">
            <label class="winsp__label">Visualization type</label>
            <VipSelect :model-value="w.type" :options="vizTypeOptions" size="sm" @update:model-value="changeType($event as WidgetType)" />
          </div>
          <div v-if="!['text','rich-text','image','filter','date-filter'].includes(w.type)" class="winsp__section">
            <label class="winsp__label">Data source</label>
            <VipSelect :model-value="w.modelId ?? ''" :options="MODELS.map((m) => ({ value: m.id, label: m.label }))" size="sm" @update:model-value="editor.patchWidget(w!.id, { modelId: $event })" />
          </div>

          <div v-for="well in wellDefs" :key="well.key" class="winsp__well" @dragover.prevent @drop="well.kind === 'dim' ? onDropDim(well.key as DimWellKey, $event) : onDropMeasure($event)">
            <div class="winsp__well-head">
              <label class="winsp__label">{{ well.label }}</label>
              <VipMenu
                v-if="well.kind === 'dim'"
                :items="availableDims(well.key as DimWellKey).map((f) => ({ key: f.id, label: f.label, icon: 'text' }))"
                @select="addDim(well.key as DimWellKey, $event)"
              >
                <template #trigger><button class="winsp__add"><VipIcon name="plus" :size="12" /></button></template>
              </VipMenu>
              <VipMenu
                v-else
                :items="availableMeasures().map((f) => ({ key: f.id, label: f.label, icon: 'hash' }))"
                @select="addMeasure"
              >
                <template #trigger><button class="winsp__add"><VipIcon name="plus" :size="12" /></button></template>
              </VipMenu>
            </div>

            <div class="winsp__chips">
              <template v-if="well.kind === 'dim'">
                <div v-for="fid in dimValues(well.key as DimWellKey)" :key="fid" class="winsp__chip">
                  <VipIcon name="text" :size="12" />
                  <span>{{ fieldLabel(fid) }}</span>
                  <button class="winsp__chip-x" @click="removeDim(well.key as DimWellKey, fid)"><VipIcon name="close" :size="11" /></button>
                </div>
              </template>
              <template v-else>
                <div v-for="v in w.wells.values ?? []" :key="v.fieldId" class="winsp__chip is-measure">
                  <span>{{ fieldLabel(v.fieldId) }}</span>
                  <select class="winsp__agg" :value="v.aggregation" @change="setAgg(v.fieldId, ($event.target as HTMLSelectElement).value as Aggregation)">
                    <option v-for="o in aggOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
                  </select>
                  <button class="winsp__chip-x" @click="removeMeasure(v.fieldId)"><VipIcon name="close" :size="11" /></button>
                </div>
              </template>
              <div v-if="(well.kind === 'dim' ? dimValues(well.key as DimWellKey).length : (w.wells.values ?? []).length) === 0" class="winsp__well-empty">
                Drop a field or click +
              </div>
            </div>
          </div>

          <div v-if="w.type === 'text' || w.type === 'rich-text' || w.type === 'image'" class="winsp__section">
            <label class="winsp__label">Content</label>
            <VipInput :model-value="w.content ?? ''" size="sm" @update:model-value="editor.patchWidget(w!.id, { content: String($event) })" />
          </div>
        </template>

        <!-- FORMAT -->
        <template v-else-if="tab === 'format'">
          <div class="winsp__section"><VipInput label="Title" :model-value="w.format.title ?? ''" size="sm" @update:model-value="patchFormat({ title: String($event) })" /></div>
          <div class="winsp__section"><VipInput label="Subtitle" :model-value="w.format.subtitle ?? ''" size="sm" @update:model-value="patchFormat({ subtitle: String($event) })" /></div>
          <div class="winsp__row"><VipSwitch :model-value="w.format.showTitle" label="Show title" @update:model-value="patchFormat({ showTitle: $event })" /></div>
          <div class="winsp__row"><VipSwitch :model-value="w.format.showLegend" label="Show legend" @update:model-value="patchFormat({ showLegend: $event })" /></div>
          <div class="winsp__row"><VipSwitch :model-value="w.format.showDataLabels" label="Data labels" @update:model-value="patchFormat({ showDataLabels: $event })" /></div>
          <div class="winsp__row"><VipSwitch :model-value="w.format.showGridlines" label="Gridlines" @update:model-value="patchFormat({ showGridlines: $event })" /></div>
          <div class="winsp__section">
            <VipSelect label="Number format" :model-value="w.format.numberStyle" size="sm" :options="[{ value: 'plain', label: 'Plain' }, { value: 'compact', label: 'Compact (1.2K)' }, { value: 'currency', label: 'Currency' }, { value: 'percent', label: 'Percent' }]" @update:model-value="patchFormat({ numberStyle: $event as 'plain' })" />
          </div>
          <div class="winsp__section"><VipInput label="Decimal places" type="number" :model-value="w.format.decimals" size="sm" @update:model-value="patchFormat({ decimals: Number($event) })" /></div>
          <div class="winsp__section">
            <VipSelect label="Color scheme" :model-value="w.format.colorScheme ?? 'default'" size="sm" :options="[{ value: 'default', label: 'VIP Default' }, { value: 'cool', label: 'Cool' }, { value: 'warm', label: 'Warm' }, { value: 'status', label: 'Status' }]" @update:model-value="patchFormat({ colorScheme: $event })" />
          </div>
          <div class="winsp__row"><VipSwitch :model-value="w.format.border" label="Border" @update:model-value="patchFormat({ border: $event })" /></div>
        </template>

        <!-- INTERACTIONS -->
        <template v-else-if="tab === 'interactions'">
          <div class="winsp__row"><VipSwitch :model-value="w.interactions.crossFilter" label="Cross-filter other visuals" @update:model-value="patchInteractions({ crossFilter: $event })" /></div>
          <div class="winsp__row"><VipSwitch :model-value="w.interactions.drillDown" label="Enable drill-down" @update:model-value="patchInteractions({ drillDown: $event })" /></div>
          <div class="winsp__row"><VipSwitch :model-value="w.interactions.tooltip" label="Show tooltips" @update:model-value="patchInteractions({ tooltip: $event })" /></div>
          <div class="winsp__row"><VipSwitch :model-value="w.interactions.exportable" label="Allow export" @update:model-value="patchInteractions({ exportable: $event })" /></div>
          <p class="winsp__hint">Drill-through to another page is a foundation; target selection connects to the backend page registry.</p>
        </template>

        <!-- GENERAL -->
        <template v-else>
          <div class="winsp__section"><VipInput label="Widget name" :model-value="w.general.name" size="sm" @update:model-value="patchGeneral({ name: String($event) })" /></div>
          <div class="winsp__section"><VipInput label="Description" :model-value="w.general.description ?? ''" size="sm" @update:model-value="patchGeneral({ description: String($event) })" /></div>
          <div class="winsp__section"><VipInput label="Accessibility label" :model-value="w.general.ariaLabel ?? ''" size="sm" help="Announced to screen readers." @update:model-value="patchGeneral({ ariaLabel: String($event) })" /></div>
          <div class="winsp__row"><VipSwitch :model-value="w.general.visible" label="Visible" @update:model-value="patchGeneral({ visible: $event })" /></div>
          <div class="winsp__row"><VipSwitch :model-value="w.general.locked" label="Lock position & size" @update:model-value="patchGeneral({ locked: $event })" /></div>
          <div class="winsp__pos">Position: col {{ w.pos.x }}, row {{ w.pos.y }} · {{ w.pos.w }}×{{ w.pos.h }}</div>
        </template>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.winsp { display: flex; flex-direction: column; height: 100%; background: var(--vip-surface-1); }
.winsp__empty { flex: 1; display: flex; align-items: center; }
.winsp__tabs { padding: var(--vip-sp-5) var(--vip-sp-5) 0; }
.winsp__tabs :deep(.vip-seg) { width: 100%; }
.winsp__tabs :deep(.vip-seg__btn) { flex: 1; justify-content: center; }
.winsp__body { flex: 1; overflow-y: auto; padding: var(--vip-sp-6); display: flex; flex-direction: column; gap: var(--vip-sp-5); }
.winsp__label { font-size: var(--vip-fs-sm); font-weight: var(--vip-fw-medium); color: var(--vip-text-secondary); }
.winsp__section { display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.winsp__row { display: flex; align-items: center; justify-content: space-between; }

.winsp__well { background: var(--vip-surface-2); border: 1px dashed var(--vip-border); border-radius: var(--vip-radius-md); padding: var(--vip-sp-4); }
.winsp__well-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--vip-sp-3); }
.winsp__add { width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center; background: var(--vip-surface-3); border: none; border-radius: var(--vip-radius-sm); color: var(--vip-text-secondary); }
.winsp__add:hover { background: var(--vip-brand-soft); color: var(--vip-brand-text); }
.winsp__chips { display: flex; flex-direction: column; gap: var(--vip-sp-2); }
.winsp__chip { display: flex; align-items: center; gap: var(--vip-sp-3); padding: var(--vip-sp-2) var(--vip-sp-3); background: var(--vip-surface-1); border: 1px solid var(--vip-border); border-radius: var(--vip-radius-sm); font-size: var(--vip-fs-sm); }
.winsp__chip.is-measure { border-color: var(--vip-brand-500); }
.winsp__chip span { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.winsp__agg { background: var(--vip-surface-3); border: none; border-radius: var(--vip-radius-xs); font-size: var(--vip-fs-2xs); color: var(--vip-text-secondary); padding: 1px 3px; }
.winsp__chip-x { width: 18px; height: 18px; flex: none; background: none; border: none; color: var(--vip-text-muted); border-radius: var(--vip-radius-xs); }
.winsp__chip-x:hover { background: var(--vip-danger-soft); color: var(--vip-danger-text); }
.winsp__well-empty { font-size: var(--vip-fs-xs); color: var(--vip-text-disabled); padding: var(--vip-sp-2); text-align: center; }
.winsp__hint { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.winsp__pos { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); font-variant-numeric: tabular-nums; }
</style>
