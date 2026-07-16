<script setup lang="ts">
import { ref, computed, toRef } from 'vue'
import { useRouter } from 'vue-router'
import { MODELS } from '@/shared/services/semanticModels'
import { createWidget } from '@/modules/dashboards/widgetFactory'
import { useWidgetData } from '@/modules/dashboards/useWidgetData'
import { useUiStore } from '@/shared/stores/ui'
import type { DashboardWidget, WidgetType } from '@/shared/types/dashboard'
import type { Aggregation, QueryFilter, SemanticField } from '@/shared/types/semantic'
import VisualRenderer from '@/shared/viz/VisualRenderer.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'

const router = useRouter()
const ui = useUiStore()

const modelId = ref('sm_sales')
const search = ref('')
const widget = ref<DashboardWidget>(build('column'))
const extraFilters = ref<QueryFilter[]>([])

function build(type: WidgetType): DashboardWidget {
  const w = createWidget(type, 0, 0, modelId.value)
  w.wells = { xAxis: ['region'], values: [{ fieldId: 'revenue', aggregation: 'sum' }] }
  w.format.showTitle = false
  return w
}

const model = computed(() => MODELS.find((m) => m.id === modelId.value) ?? MODELS[0])
const dims = computed(() => model.value.fields.filter((f) => (f.role === 'dimension' || f.role === 'time') && match(f)))
const measures = computed(() => model.value.fields.filter((f) => (f.role === 'measure' || f.role === 'metric') && match(f)))
function match(f: SemanticField) {
  const q = search.value.trim().toLowerCase()
  return !q || f.label.toLowerCase().includes(q)
}

const widgetRef = toRef(widget)
const filtersRef = toRef(extraFilters)
const { result, loading, error } = useWidgetData(widgetRef, filtersRef)

const chartTypes: { value: WidgetType; icon: string; label: string }[] = [
  { value: 'column', icon: 'chart', label: 'Column' },
  { value: 'bar', icon: 'chart', label: 'Bar' },
  { value: 'line', icon: 'trendUp', label: 'Line' },
  { value: 'area', icon: 'trendUp', label: 'Area' },
  { value: 'pie', icon: 'pieChart', label: 'Pie' },
  { value: 'donut', icon: 'pieChart', label: 'Donut' },
  { value: 'table', icon: 'table', label: 'Table' },
  { value: 'kpi', icon: 'target', label: 'KPI' },
]

function setType(t: WidgetType) {
  widget.value = { ...widget.value, type: t }
}
function changeModel(id: string) {
  modelId.value = id
  widget.value = build(widget.value.type)
}
function isActiveDim(id: string): boolean {
  return (widget.value.wells.xAxis ?? []).includes(id) || (widget.value.wells.category ?? []).includes(id)
}
function toggleDim(f: SemanticField) {
  const key = ['pie', 'donut'].includes(widget.value.type) ? 'category' : 'xAxis'
  const cur = (widget.value.wells[key] as string[] | undefined) ?? []
  const next = cur.includes(f.id) ? cur.filter((x) => x !== f.id) : [...cur, f.id]
  widget.value = { ...widget.value, wells: { ...widget.value.wells, [key]: next } }
}
function isActiveMeasure(id: string): boolean {
  return (widget.value.wells.values ?? []).some((v) => v.fieldId === id)
}
function toggleMeasure(f: SemanticField) {
  const cur = widget.value.wells.values ?? []
  const exists = cur.some((v) => v.fieldId === f.id)
  const next = exists ? cur.filter((v) => v.fieldId !== f.id) : [...cur, { fieldId: f.id, aggregation: (f.defaultAggregation ?? 'sum') as Aggregation }]
  widget.value = { ...widget.value, wells: { ...widget.value.wells, values: next } }
}

const showData = ref(false)
function save() { ui.pushToast({ kind: 'success', title: 'Saved as insight', message: 'Available in Insights → Saved.' }) }
function pin() { ui.pushToast({ kind: 'success', title: 'Pinned to dashboard' }) }
function exportData() { ui.pushToast({ kind: 'info', title: 'Export', message: 'CSV export is a backend dependency.' }) }

function roleIcon(role: SemanticField['role']): string {
  return role === 'measure' ? 'hash' : role === 'metric' ? 'target' : role === 'time' ? 'calendar' : 'text'
}
</script>

<template>
  <div class="explore">
    <header class="explore__toolbar">
      <div class="explore__tb-left">
        <VipButton variant="ghost" size="sm" icon="chevronLeft" @click="router.push('/insights')" />
        <VipIcon name="trendUp" :size="18" />
        <h1 class="explore__title">Explore</h1>
        <VipBadge tone="brand" size="sm">Ad-hoc analysis</VipBadge>
      </div>
      <div class="explore__tb-right">
        <VipButton variant="ghost" size="sm" :icon="'table'" :active="showData" @click="showData = !showData">Data</VipButton>
        <VipButton variant="secondary" size="sm" icon="pin" @click="pin">Pin</VipButton>
        <VipButton variant="secondary" size="sm" icon="download" @click="exportData">Export</VipButton>
        <VipButton variant="primary" size="sm" icon="star" @click="save">Save as insight</VipButton>
      </div>
    </header>

    <div class="explore__body">
      <!-- fields -->
      <aside class="explore__fields">
        <div class="explore__model">
          <VipSelect :model-value="modelId" :options="MODELS.map((m) => ({ value: m.id, label: m.label }))" size="sm" @update:model-value="changeModel" />
        </div>
        <div class="explore__search"><VipInput v-model="search" icon="search" placeholder="Search fields…" size="sm" /></div>
        <div class="explore__field-group">
          <div class="explore__fg-label">Dimensions</div>
          <button v-for="f in dims" :key="f.id" class="explore__field" :class="{ 'is-active': isActiveDim(f.id) }" @click="toggleDim(f)">
            <VipIcon :name="roleIcon(f.role)" :size="13" /><span>{{ f.label }}</span>
            <VipIcon v-if="isActiveDim(f.id)" name="check" :size="13" class="explore__check" />
          </button>
        </div>
        <div class="explore__field-group">
          <div class="explore__fg-label">Measures</div>
          <button v-for="f in measures" :key="f.id" class="explore__field is-measure" :class="{ 'is-active': isActiveMeasure(f.id) }" @click="toggleMeasure(f)">
            <VipIcon :name="roleIcon(f.role)" :size="13" /><span>{{ f.label }}</span>
            <VipIcon v-if="isActiveMeasure(f.id)" name="check" :size="13" class="explore__check" />
          </button>
        </div>
      </aside>

      <!-- canvas -->
      <main class="explore__main">
        <div class="explore__chart-types">
          <button
            v-for="t in chartTypes"
            :key="t.value"
            class="explore__ctype"
            :class="{ 'is-active': widget.type === t.value }"
            :title="t.label"
            @click="setType(t.value)"
          ><VipIcon :name="t.icon" :size="16" /></button>
        </div>

        <div class="explore__visual">
          <VisualRenderer :widget="widget" :result="result" :loading="loading" :error="error" />
        </div>

        <div v-if="showData && result" class="explore__data">
          <table>
            <thead><tr><th v-for="c in result.columns" :key="c.key">{{ c.label }}</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in result.rows.slice(0, 50)" :key="i">
                <td v-for="c in result.columns" :key="c.key">{{ r[c.key] }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.explore { display: flex; flex-direction: column; height: 100vh; width: 100%; background: var(--vip-bg-canvas); }
.explore__toolbar { display: flex; align-items: center; justify-content: space-between; height: 52px; padding: 0 var(--vip-sp-5); background: var(--vip-surface-1); border-bottom: 1px solid var(--vip-border); flex: none; }
.explore__tb-left { display: flex; align-items: center; gap: var(--vip-sp-4); }
.explore__title { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); }
.explore__tb-right { display: flex; align-items: center; gap: var(--vip-sp-3); }
.explore__body { flex: 1; display: flex; min-height: 0; }
.explore__fields { width: 260px; flex: none; border-right: 1px solid var(--vip-border); background: var(--vip-surface-1); overflow-y: auto; padding: var(--vip-sp-5); }
.explore__model, .explore__search { margin-bottom: var(--vip-sp-5); }
.explore__field-group { margin-bottom: var(--vip-sp-6); }
.explore__fg-label { font-size: var(--vip-fs-2xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-disabled); margin-bottom: var(--vip-sp-3); }
.explore__field { display: flex; align-items: center; gap: var(--vip-sp-3); width: 100%; padding: var(--vip-sp-3) var(--vip-sp-4); background: none; border: none; border-radius: var(--vip-radius-sm); color: var(--vip-text-secondary); font-size: var(--vip-fs-sm); text-align: left; }
.explore__field span { flex: 1; }
.explore__field:hover { background: var(--vip-surface-hover); }
.explore__field.is-active { background: var(--vip-brand-soft); color: var(--vip-brand-text); }
.explore__field.is-measure.is-active { color: var(--vip-brand-text); }
.explore__check { color: var(--vip-brand-text); }
.explore__main { flex: 1; min-width: 0; display: flex; flex-direction: column; padding: var(--vip-sp-6); gap: var(--vip-sp-5); }
.explore__chart-types { display: flex; gap: var(--vip-sp-2); }
.explore__ctype { width: 34px; height: 30px; display: inline-flex; align-items: center; justify-content: center; background: var(--vip-surface-1); border: 1px solid var(--vip-border); border-radius: var(--vip-radius-md); color: var(--vip-text-muted); }
.explore__ctype:hover { border-color: var(--vip-border-strong); color: var(--vip-text-primary); }
.explore__ctype.is-active { background: var(--vip-brand-soft); border-color: var(--vip-brand-500); color: var(--vip-brand-text); }
.explore__visual { flex: 1; min-height: 0; background: var(--vip-surface-1); border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-lg); padding: var(--vip-sp-6); }
.explore__data { max-height: 220px; overflow: auto; background: var(--vip-surface-1); border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-lg); }
.explore__data table { width: 100%; border-collapse: collapse; font-size: var(--vip-fs-sm); }
.explore__data th { position: sticky; top: 0; background: var(--vip-surface-1); text-align: left; padding: var(--vip-sp-3) var(--vip-sp-5); color: var(--vip-text-muted); font-size: var(--vip-fs-xs); border-bottom: 1px solid var(--vip-border); }
.explore__data td { padding: var(--vip-sp-3) var(--vip-sp-5); border-bottom: 1px solid var(--vip-border-subtle); color: var(--vip-text-secondary); }
</style>
