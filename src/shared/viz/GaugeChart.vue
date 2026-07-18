<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ value: number; max?: number; label?: string; suffix?: string }>(), {
  max: 100,
})
const pct = computed(() => Math.min(1, Math.max(0, props.value / props.max)))
const R = 70
const CX = 100
const CY = 100
const startA = Math.PI
const endA = 2 * Math.PI
function pointOnArc(frac: number) {
  const a = startA + (endA - startA) * frac
  return { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) }
}
const bg = `M ${pointOnArc(0).x} ${pointOnArc(0).y} A ${R} ${R} 0 0 1 ${pointOnArc(1).x} ${pointOnArc(1).y}`
const fg = computed(() => {
  const end = pointOnArc(pct.value)
  const large = pct.value > 0.5 ? 1 : 0
  return `M ${pointOnArc(0).x} ${pointOnArc(0).y} A ${R} ${R} 0 ${large} 1 ${end.x} ${end.y}`
})
const color = computed(() =>
  pct.value > 0.75 ? 'var(--vip-success)' : pct.value > 0.4 ? 'var(--vip-warning)' : 'var(--vip-danger)',
)
</script>

<template>
  <div class="gauge">
    <svg viewBox="0 0 200 120" class="gauge__svg" role="img">
      <path :d="bg" fill="none" stroke="var(--vip-surface-3)" stroke-width="14" stroke-linecap="round" />
      <path :d="fg" fill="none" :stroke="color" stroke-width="14" stroke-linecap="round" />
      <text :x="CX" :y="CY - 6" text-anchor="middle" class="gauge__val">{{ value.toFixed(0) }}{{ suffix }}</text>
      <text v-if="label" :x="CX" :y="CY + 12" text-anchor="middle" class="gauge__label">{{ label }}</text>
    </svg>
  </div>
</template>

<style scoped>
.gauge {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.gauge__svg {
  width: 100%;
  max-height: 100%;
}
.gauge__val {
  fill: var(--vip-text-primary);
  font-size: 26px;
  font-weight: 700;
}
.gauge__label {
  fill: var(--vip-text-muted);
  font-size: 11px;
}
</style>
