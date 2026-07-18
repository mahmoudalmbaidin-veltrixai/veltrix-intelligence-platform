<script setup lang="ts">
import { computed } from 'vue'
import type { Slice } from './chartData'
import { schemeColor } from './colors'
import { formatNumber } from '@/shared/lib/format'
import type { NumberFormat } from '@/shared/types/semantic'

const props = withDefaults(
  defineProps<{
    slices: Slice[]
    donut?: boolean
    scheme?: string
    showLegend?: boolean
    format?: Partial<NumberFormat>
  }>(),
  { showLegend: true },
)

const total = computed(() => props.slices.reduce((s, x) => s + x.value, 0) || 1)
const R = 80
const CX = 100
const CY = 100
const innerR = computed(() => (props.donut ? 48 : 0))

const arcs = computed(() => {
  let angle = -Math.PI / 2
  return props.slices.map((s, i) => {
    const frac = s.value / total.value
    const start = angle
    const end = angle + frac * Math.PI * 2
    angle = end
    const large = end - start > Math.PI ? 1 : 0
    const x1 = CX + R * Math.cos(start)
    const y1 = CY + R * Math.sin(start)
    const x2 = CX + R * Math.cos(end)
    const y2 = CY + R * Math.sin(end)
    let d = `M ${CX} ${CY} L ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2} Z`
    if (props.donut) {
      const ir = innerR.value
      const ix1 = CX + ir * Math.cos(start)
      const iy1 = CY + ir * Math.sin(start)
      const ix2 = CX + ir * Math.cos(end)
      const iy2 = CY + ir * Math.sin(end)
      d = `M ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2} L ${ix2} ${iy2} A ${ir} ${ir} 0 ${large} 0 ${ix1} ${iy1} Z`
    }
    return { d, color: schemeColor(props.scheme, i), label: s.label, value: s.value, pct: frac }
  })
})

function fmt(v: number): string {
  return formatNumber(v, props.format ?? { style: 'compact' })
}
</script>

<template>
  <div class="pie">
    <svg viewBox="0 0 200 200" class="pie__svg" role="img">
      <path v-for="(a, i) in arcs" :key="i" :d="a.d" :fill="a.color" class="pie__arc" />
      <text v-if="donut" :x="CX" :y="CY - 4" text-anchor="middle" class="pie__center-val">{{ fmt(total) }}</text>
      <text v-if="donut" :x="CX" :y="CY + 12" text-anchor="middle" class="pie__center-label">Total</text>
    </svg>
    <div v-if="showLegend" class="pie__legend">
      <div v-for="(a, i) in arcs" :key="i" class="pie__legend-item">
        <span class="pie__dot" :style="{ background: a.color }" />
        <span class="pie__name">{{ a.label }}</span>
        <span class="pie__val">{{ (a.pct * 100).toFixed(0) }}%</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pie {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-6);
  width: 100%;
  height: 100%;
}
.pie__svg {
  height: 100%;
  max-height: 220px;
  aspect-ratio: 1;
}
.pie__arc {
  stroke: var(--vip-surface-1);
  stroke-width: 1.5;
  transition: opacity var(--vip-motion-fast);
}
.pie__arc:hover {
  opacity: 0.85;
}
.pie__center-val {
  fill: var(--vip-text-primary);
  font-size: 18px;
  font-weight: 600;
}
.pie__center-label {
  fill: var(--vip-text-muted);
  font-size: 10px;
}
.pie__legend {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
  min-width: 0;
}
.pie__legend-item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-xs);
}
.pie__dot {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  flex: none;
}
.pie__name {
  color: var(--vip-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pie__val {
  margin-left: auto;
  color: var(--vip-text-muted);
  font-variant-numeric: tabular-nums;
}
</style>
