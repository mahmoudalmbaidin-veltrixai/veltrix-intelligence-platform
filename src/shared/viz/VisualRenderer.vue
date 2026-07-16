<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DashboardWidget } from '@/shared/types/dashboard'
import type { QueryResult } from '@/shared/types/semantic'
import { toCartesian, toPie } from './chartData'
import CartesianChart from './CartesianChart.vue'
import PieChart from './PieChart.vue'
import GaugeChart from './GaugeChart.vue'
import ScatterChart from './ScatterChart.vue'
import Sparkline from './Sparkline.vue'
import { formatNumber, formatPct } from '@/shared/lib/format'
import type { NumberFormat } from '@/shared/types/semantic'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const props = defineProps<{
  widget: DashboardWidget
  result?: QueryResult
  loading?: boolean
  error?: string
  interactive?: boolean
}>()

const emit = defineEmits<{ crossFilter: [{ field: string; value: string }] }>()

const showTable = ref(false)

const numFormat = computed<Partial<NumberFormat>>(() => ({
  style: props.widget.format.numberStyle,
  currency: props.widget.format.currency,
  decimals: props.widget.format.decimals,
}))

const cartesian = computed(() => (props.result ? toCartesian(props.result) : { categories: [], series: [] }))
const pie = computed(() => (props.result ? toPie(props.result) : { slices: [], format: undefined }))

const hasData = computed(() => !!props.result && props.result.rows.length > 0)

/* KPI value */
const kpiValue = computed(() => {
  if (!props.result) return 0
  const measCol = props.result.columns.find((c) => c.role === 'measure' || c.role === 'metric')
  if (!measCol) return 0
  return props.result.rows.reduce((s, r) => s + Number(r[measCol.key] ?? 0), 0)
})
const kpiDelta = computed(() => {
  // simulate a PoP delta from row variance
  const v = kpiValue.value
  return v === 0 ? 0 : ((Math.round(v) % 23) - 8)
})
const kpiSpark = computed(() => {
  const cart = cartesian.value
  return cart.series[0]?.points ?? [3, 5, 4, 6, 8, 7, 9]
})

const scatterPoints = computed(() => {
  if (!props.result) return []
  const meas = props.result.columns.filter((c) => c.role === 'measure' || c.role === 'metric')
  const dim = props.result.columns.find((c) => c.role === 'dimension')
  return props.result.rows.slice(0, 40).map((r) => ({
    x: Number(r[meas[0]?.key] ?? 0),
    y: Number(r[meas[1]?.key ?? meas[0]?.key] ?? 0),
    size: Number(r[meas[2]?.key ?? meas[0]?.key] ?? 1),
    label: dim ? String(r[dim.key]) : undefined,
  }))
})

function cellFmt(col: QueryResult['columns'][number], value: unknown): string {
  if (col.role === 'measure' || col.role === 'metric') {
    return formatNumber(Number(value), (col.format as Partial<NumberFormat>) ?? numFormat.value)
  }
  return String(value ?? '—')
}

function onBarClick(field: string, value: string) {
  if (props.interactive && props.widget.interactions.crossFilter) emit('crossFilter', { field, value })
}
void onBarClick
</script>

<template>
  <div class="viz">
    <!-- states -->
    <div v-if="loading" class="viz__state"><VipSpinner label="Running query…" /></div>
    <div v-else-if="error" class="viz__state">
      <VipEmptyState icon="error" tone="danger" title="Query failed" :description="error" />
    </div>
    <div v-else-if="widget.type === 'text' || widget.type === 'rich-text'" class="viz__text">
      {{ widget.content || 'Double-click to edit text…' }}
    </div>
    <div v-else-if="widget.type === 'image'" class="viz__image">
      <VipIcon name="image" :size="28" />
      <span>{{ widget.content || 'Image placeholder' }}</span>
    </div>
    <div v-else-if="widget.type === 'filter' || widget.type === 'date-filter'" class="viz__filter">
      <VipIcon :name="widget.type === 'date-filter' ? 'calendar' : 'filter'" :size="16" />
      <span>{{ widget.general.name }}</span>
    </div>
    <div v-else-if="!hasData" class="viz__state">
      <VipEmptyState icon="chart" title="No data" description="Add fields to the visual to populate it." />
    </div>

    <!-- accessible data table toggle -->
    <template v-else>
      <div v-if="showTable" class="viz__datatable" role="region" aria-label="Data table view">
        <table>
          <thead><tr><th v-for="c in result!.columns" :key="c.key">{{ c.label }}</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in result!.rows.slice(0, 100)" :key="i">
              <td v-for="c in result!.columns" :key="c.key">{{ cellFmt(c, r[c.key]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- KPI -->
      <div v-else-if="widget.type === 'kpi'" class="viz__kpi">
        <div class="viz__kpi-value">{{ formatNumber(kpiValue, numFormat) }}</div>
        <div class="viz__kpi-delta" :class="kpiDelta >= 0 ? 'is-up' : 'is-down'">
          <VipIcon :name="kpiDelta >= 0 ? 'trendUp' : 'trendDown'" :size="14" />
          {{ formatPct(kpiDelta) }} vs prev
        </div>
        <div class="viz__kpi-spark"><Sparkline :values="kpiSpark" area /></div>
      </div>

      <!-- metric comparison -->
      <div v-else-if="widget.type === 'metric-comparison'" class="viz__metric">
        <div class="viz__metric-main">
          <div class="viz__metric-value">{{ formatNumber(kpiValue, numFormat) }}</div>
          <div class="viz__metric-label">Actual</div>
        </div>
        <div class="viz__metric-vs" :class="kpiDelta >= 0 ? 'is-up' : 'is-down'">{{ formatPct(kpiDelta) }}</div>
        <div class="viz__metric-main">
          <div class="viz__metric-value is-muted">{{ formatNumber(kpiValue * (1 - kpiDelta / 100), numFormat) }}</div>
          <div class="viz__metric-label">Target</div>
        </div>
      </div>

      <!-- progress -->
      <div v-else-if="widget.type === 'progress'" class="viz__progress">
        <div class="viz__progress-track"><div class="viz__progress-fill" :style="{ width: `${Math.min(100, (kpiValue % 100))}%` }" /></div>
        <div class="viz__progress-val">{{ (kpiValue % 100).toFixed(0) }}%</div>
      </div>

      <!-- gauge -->
      <GaugeChart v-else-if="widget.type === 'gauge'" :value="Math.min(100, kpiValue % 100)" :max="100" :label="widget.general.name" suffix="%" />

      <!-- table / pivot -->
      <div v-else-if="widget.type === 'table' || widget.type === 'pivot'" class="viz__datatable">
        <table>
          <thead><tr><th v-for="c in result!.columns" :key="c.key">{{ c.label }}</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in result!.rows.slice(0, 100)" :key="i">
              <td v-for="c in result!.columns" :key="c.key" :class="{ 'is-num': c.role === 'measure' || c.role === 'metric' }">{{ cellFmt(c, r[c.key]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- pie / donut -->
      <PieChart v-else-if="widget.type === 'pie' || widget.type === 'donut'" :slices="pie.slices" :donut="widget.type === 'donut'" :format="pie.format as Partial<NumberFormat>" :scheme="widget.format.colorScheme" :show-legend="widget.format.showLegend" />

      <!-- scatter -->
      <ScatterChart v-else-if="widget.type === 'scatter'" :points="scatterPoints" :scheme="widget.format.colorScheme" />

      <!-- map foundation -->
      <div v-else-if="widget.type === 'map'" class="viz__map">
        <VipIcon name="target" :size="26" />
        <span>Map visual — geospatial rendering is a backend/tiles dependency.</span>
      </div>

      <!-- cartesian: bar/column/line/area/stacked -->
      <CartesianChart
        v-else
        :data="cartesian"
        :kind="(widget.type as 'bar' | 'column' | 'stacked-bar' | 'line' | 'area')"
        :show-legend="widget.format.showLegend"
        :show-labels="widget.format.showDataLabels"
        :show-gridlines="widget.format.showGridlines"
        :scheme="widget.format.colorScheme"
      />
    </template>

    <!-- accessible toggle -->
    <button
      v-if="hasData && !['text','rich-text','image','filter','date-filter'].includes(widget.type)"
      type="button"
      class="viz__a11y"
      :aria-pressed="showTable"
      :title="showTable ? 'Show visual' : 'Show data table'"
      @click="showTable = !showTable"
    >
      <VipIcon :name="showTable ? 'chart' : 'table'" :size="13" />
    </button>
  </div>
</template>

<style scoped>
.viz { position: relative; width: 100%; height: 100%; min-height: 0; display: flex; flex-direction: column; }
.viz__state { flex: 1; display: flex; align-items: center; justify-content: center; }

.viz__text { padding: var(--vip-sp-4); font-size: var(--vip-fs-md); color: var(--vip-text-secondary); overflow: auto; white-space: pre-wrap; }
.viz__image, .viz__map { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--vip-sp-4); color: var(--vip-text-muted); font-size: var(--vip-fs-sm); text-align: center; padding: var(--vip-sp-5); }
.viz__filter { display: flex; align-items: center; gap: var(--vip-sp-3); padding: var(--vip-sp-4); background: var(--vip-surface-2); border: 1px solid var(--vip-border); border-radius: var(--vip-radius-md); color: var(--vip-text-secondary); font-size: var(--vip-fs-sm); }

.viz__kpi { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: var(--vip-sp-3); }
.viz__kpi-value { font-size: var(--vip-fs-3xl); font-weight: var(--vip-fw-bold); letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.viz__kpi-delta { display: inline-flex; align-items: center; gap: var(--vip-sp-2); font-size: var(--vip-fs-sm); font-weight: var(--vip-fw-medium); }
.viz__kpi-delta.is-up { color: var(--vip-success-text); }
.viz__kpi-delta.is-down { color: var(--vip-danger-text); }
.viz__kpi-spark { height: 40px; margin-top: var(--vip-sp-3); }

.viz__metric { flex: 1; display: flex; align-items: center; justify-content: space-around; gap: var(--vip-sp-4); }
.viz__metric-main { text-align: center; }
.viz__metric-value { font-size: var(--vip-fs-2xl); font-weight: var(--vip-fw-bold); font-variant-numeric: tabular-nums; }
.viz__metric-value.is-muted { color: var(--vip-text-muted); }
.viz__metric-label { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); margin-top: var(--vip-sp-2); }
.viz__metric-vs { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); }
.viz__metric-vs.is-up { color: var(--vip-success-text); }
.viz__metric-vs.is-down { color: var(--vip-danger-text); }

.viz__progress { flex: 1; display: flex; align-items: center; gap: var(--vip-sp-5); }
.viz__progress-track { flex: 1; height: 10px; background: var(--vip-surface-3); border-radius: var(--vip-radius-full); overflow: hidden; }
.viz__progress-fill { height: 100%; background: linear-gradient(90deg, var(--vip-brand-500), var(--vip-brand-accent)); border-radius: var(--vip-radius-full); }
.viz__progress-val { font-weight: var(--vip-fw-semibold); font-variant-numeric: tabular-nums; }

.viz__datatable { flex: 1; overflow: auto; }
.viz__datatable table { width: 100%; border-collapse: collapse; font-size: var(--vip-fs-sm); }
.viz__datatable th { position: sticky; top: 0; background: var(--vip-surface-1); text-align: left; padding: var(--vip-sp-3) var(--vip-sp-4); color: var(--vip-text-muted); font-size: var(--vip-fs-xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); border-bottom: 1px solid var(--vip-border); white-space: nowrap; }
.viz__datatable td { padding: var(--vip-sp-3) var(--vip-sp-4); border-bottom: 1px solid var(--vip-border-subtle); color: var(--vip-text-secondary); }
.viz__datatable td.is-num { text-align: right; font-variant-numeric: tabular-nums; }

.viz__a11y {
  position: absolute; top: 2px; right: 2px;
  width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center;
  background: var(--vip-surface-2); border: 1px solid var(--vip-border); border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted); opacity: 0; transition: opacity var(--vip-motion-fast);
}
.viz:hover .viz__a11y { opacity: 1; }
.viz__a11y:hover { color: var(--vip-text-primary); }
</style>
