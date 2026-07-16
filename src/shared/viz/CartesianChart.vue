<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CartesianData } from './chartData'
import { schemeColor } from './colors'
import { formatNumber } from '@/shared/lib/format'
import type { NumberFormat } from '@/shared/types/semantic'

const props = withDefaults(
  defineProps<{
    data: CartesianData
    kind: 'bar' | 'column' | 'stacked-bar' | 'line' | 'area'
    showLegend?: boolean
    showLabels?: boolean
    showGridlines?: boolean
    scheme?: string
  }>(),
  { showLegend: true, showGridlines: true },
)

const W = 640
const H = 320
const PAD = { top: 16, right: 20, bottom: 40, left: 56 }
const plotW = W - PAD.left - PAD.right
const plotH = H - PAD.top - PAD.bottom

const hover = ref<{ x: number; y: number; label: string; rows: { name: string; value: number; color: string }[] } | null>(null)

const isHorizontal = computed(() => props.kind === 'bar' || props.kind === 'stacked-bar')
const isStacked = computed(() => props.kind === 'stacked-bar')

const maxValue = computed(() => {
  if (isStacked.value) {
    return Math.max(
      1,
      ...props.data.categories.map((_, ci) => props.data.series.reduce((sum, s) => sum + (s.points[ci] ?? 0), 0)),
    )
  }
  return Math.max(1, ...props.data.series.flatMap((s) => s.points))
})

const ticks = computed(() => {
  const n = 4
  return Array.from({ length: n + 1 }, (_, i) => (maxValue.value / n) * i)
})

function fmt(v: number): string {
  return formatNumber(v, (props.data.measureFormat as Partial<NumberFormat>) ?? { style: 'compact' })
}

const cats = computed(() => props.data.categories)
const groupCount = computed(() => cats.value.length)
const seriesCount = computed(() => props.data.series.length)

/* ---- column/bar geometry ---- */
function barGeom(ci: number, si: number, value: number) {
  const bandW = (isHorizontal.value ? plotH : plotW) / groupCount.value
  const inner = bandW * 0.7
  const each = isStacked.value ? inner : inner / seriesCount.value
  if (isHorizontal.value) {
    const y = PAD.top + ci * bandW + (bandW - inner) / 2 + (isStacked.value ? 0 : si * each)
    const len = (value / maxValue.value) * plotW
    let x = PAD.left
    if (isStacked.value) {
      const prior = props.data.series.slice(0, si).reduce((s, ser) => s + (ser.points[ci] ?? 0), 0)
      x = PAD.left + (prior / maxValue.value) * plotW
    }
    return { x, y, width: len, height: isStacked.value ? inner : each * 0.86 }
  } else {
    const x = PAD.left + ci * bandW + (bandW - inner) / 2 + (isStacked.value ? 0 : si * each)
    const len = (value / maxValue.value) * plotH
    let y = PAD.top + plotH - len
    if (isStacked.value) {
      const prior = props.data.series.slice(0, si).reduce((s, ser) => s + (ser.points[ci] ?? 0), 0)
      y = PAD.top + plotH - ((prior + value) / maxValue.value) * plotH
    }
    return { x, y, width: isStacked.value ? inner : each * 0.86, height: len }
  }
}

/* ---- line/area geometry ---- */
function linePoints(si: number): string {
  const s = props.data.series[si]
  const bandW = plotW / Math.max(1, groupCount.value - (groupCount.value === 1 ? 0 : 1))
  return s.points
    .map((v, ci) => {
      const x = groupCount.value === 1 ? PAD.left + plotW / 2 : PAD.left + ci * bandW
      const y = PAD.top + plotH - (v / maxValue.value) * plotH
      return `${x},${y}`
    })
    .join(' ')
}
function areaPath(si: number): string {
  const pts = linePoints(si)
  if (!pts) return ''
  const arr = pts.split(' ')
  const first = arr[0].split(',')
  const last = arr[arr.length - 1].split(',')
  return `M ${first[0]},${PAD.top + plotH} L ${pts.replace(/ /g, ' L ')} L ${last[0]},${PAD.top + plotH} Z`
}

function catX(ci: number): number {
  const bandW = plotW / Math.max(1, groupCount.value - (groupCount.value === 1 ? 0 : 1))
  return groupCount.value === 1 ? PAD.left + plotW / 2 : PAD.left + ci * bandW
}

function onMove(ci: number, evt: MouseEvent) {
  const rows = props.data.series.map((s, si) => ({ name: s.name, value: s.points[ci] ?? 0, color: schemeColor(props.scheme, si) }))
  hover.value = { x: evt.offsetX, y: evt.offsetY, label: cats.value[ci], rows }
}
</script>

<template>
  <div class="cart">
    <svg :viewBox="`0 0 ${W} ${H}`" class="cart__svg" preserveAspectRatio="xMidYMid meet" role="img">
      <!-- gridlines + axis ticks -->
      <g v-if="!isHorizontal">
        <g v-for="(t, i) in ticks" :key="i">
          <line
            v-if="showGridlines"
            :x1="PAD.left" :x2="W - PAD.right"
            :y1="PAD.top + plotH - (t / maxValue) * plotH" :y2="PAD.top + plotH - (t / maxValue) * plotH"
            class="cart__grid"
          />
          <text :x="PAD.left - 8" :y="PAD.top + plotH - (t / maxValue) * plotH + 4" class="cart__tick" text-anchor="end">{{ fmt(t) }}</text>
        </g>
      </g>
      <g v-else>
        <g v-for="(t, i) in ticks" :key="i">
          <line v-if="showGridlines" :x1="PAD.left + (t / maxValue) * plotW" :x2="PAD.left + (t / maxValue) * plotW" :y1="PAD.top" :y2="PAD.top + plotH" class="cart__grid" />
          <text :x="PAD.left + (t / maxValue) * plotW" :y="H - PAD.bottom + 16" class="cart__tick" text-anchor="middle">{{ fmt(t) }}</text>
        </g>
      </g>

      <!-- bars -->
      <template v-if="kind === 'bar' || kind === 'column' || kind === 'stacked-bar'">
        <template v-for="(s, si) in data.series" :key="s.key">
          <rect
            v-for="(v, ci) in s.points"
            :key="ci"
            v-bind="barGeom(ci, si, v)"
            :fill="schemeColor(scheme, si)"
            class="cart__bar"
            rx="2"
            @mousemove="onMove(ci, $event)"
            @mouseleave="hover = null"
          />
        </template>
      </template>

      <!-- area fill -->
      <template v-if="kind === 'area'">
        <path v-for="(s, si) in data.series" :key="`a-${s.key}`" :d="areaPath(si)" :fill="schemeColor(scheme, si)" class="cart__area" />
      </template>

      <!-- lines -->
      <template v-if="kind === 'line' || kind === 'area'">
        <polyline v-for="(s, si) in data.series" :key="`l-${s.key}`" :points="linePoints(si)" :stroke="schemeColor(scheme, si)" fill="none" stroke-width="2.2" class="cart__line" />
        <template v-for="(s, si) in data.series" :key="`d-${s.key}`">
          <circle v-for="(v, ci) in s.points" :key="ci" :cx="catX(ci)" :cy="PAD.top + plotH - (v / maxValue) * plotH" r="3" :fill="schemeColor(scheme, si)" class="cart__dot" />
        </template>
      </template>

      <!-- category labels -->
      <g v-if="!isHorizontal">
        <text v-for="(c, ci) in cats" :key="ci" :x="kind === 'line' || kind === 'area' ? catX(ci) : PAD.left + ci * (plotW / groupCount) + (plotW / groupCount) / 2" :y="H - PAD.bottom + 18" class="cart__cat" text-anchor="middle">{{ c }}</text>
      </g>
      <g v-else>
        <text v-for="(c, ci) in cats" :key="ci" :x="PAD.left - 8" :y="PAD.top + ci * (plotH / groupCount) + (plotH / groupCount) / 2 + 4" class="cart__cat" text-anchor="end">{{ c }}</text>
      </g>

      <!-- hover guide -->
      <line v-if="hover && (kind === 'line' || kind === 'area')" :x1="hover.x" :x2="hover.x" :y1="PAD.top" :y2="PAD.top + plotH" class="cart__guide" />
    </svg>

    <div v-if="hover" class="cart__tip" :style="{ left: `${(hover.x / W) * 100}%`, top: `${(hover.y / H) * 100}%` }">
      <div class="cart__tip-label">{{ hover.label }}</div>
      <div v-for="r in hover.rows" :key="r.name" class="cart__tip-row">
        <span class="cart__tip-dot" :style="{ background: r.color }" />
        <span class="cart__tip-name">{{ r.name }}</span>
        <span class="cart__tip-val">{{ fmt(r.value) }}</span>
      </div>
    </div>

    <div v-if="showLegend && data.series.length > 1" class="cart__legend">
      <span v-for="(s, si) in data.series" :key="s.key" class="cart__legend-item">
        <span class="cart__legend-dot" :style="{ background: schemeColor(scheme, si) }" />{{ s.name }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.cart { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
.cart__svg { width: 100%; flex: 1; min-height: 0; overflow: visible; }
.cart__grid { stroke: var(--vip-grid-line); stroke-width: 1; }
.cart__tick, .cart__cat { fill: var(--vip-text-muted); font-size: 10px; font-family: var(--vip-font-sans); }
.cart__bar { transition: opacity var(--vip-motion-fast); cursor: pointer; }
.cart__bar:hover { opacity: 0.82; }
.cart__area { opacity: 0.14; }
.cart__line { stroke-linejoin: round; stroke-linecap: round; }
.cart__guide { stroke: var(--vip-border-strong); stroke-dasharray: 3 3; }
.cart__legend { display: flex; flex-wrap: wrap; gap: var(--vip-sp-5); justify-content: center; padding-top: var(--vip-sp-4); }
.cart__legend-item { display: inline-flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-xs); color: var(--vip-text-secondary); }
.cart__legend-dot { width: 9px; height: 9px; border-radius: 2px; }
.cart__tip {
  position: absolute; transform: translate(-50%, -110%); pointer-events: none;
  background: var(--vip-surface-3); border: 1px solid var(--vip-border); border-radius: var(--vip-radius-sm);
  padding: var(--vip-sp-3) var(--vip-sp-4); box-shadow: var(--vip-shadow-md); z-index: 5; min-width: 120px;
}
.cart__tip-label { font-size: var(--vip-fs-xs); font-weight: var(--vip-fw-semibold); margin-bottom: var(--vip-sp-2); }
.cart__tip-row { display: flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-xs); }
.cart__tip-dot { width: 8px; height: 8px; border-radius: 2px; }
.cart__tip-name { color: var(--vip-text-muted); }
.cart__tip-val { margin-left: auto; font-weight: var(--vip-fw-medium); font-variant-numeric: tabular-nums; }
</style>
