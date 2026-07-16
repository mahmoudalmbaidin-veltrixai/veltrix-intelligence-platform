<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(
  defineProps<{ values: number[]; color?: string; area?: boolean; height?: number }>(),
  { color: 'var(--vip-brand-500)', height: 36 },
)
const W = 120
const max = computed(() => Math.max(...props.values, 1))
const min = computed(() => Math.min(...props.values, 0))
const range = computed(() => max.value - min.value || 1)
const pts = computed(() =>
  props.values
    .map((v, i) => {
      const x = (i / Math.max(1, props.values.length - 1)) * W
      const y = props.height - ((v - min.value) / range.value) * (props.height - 4) - 2
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' '),
)
const areaPath = computed(() => `M 0,${props.height} L ${pts.value.replace(/ /g, ' L ')} L ${W},${props.height} Z`)
</script>

<template>
  <svg :viewBox="`0 0 ${W} ${height}`" class="spark" preserveAspectRatio="none" aria-hidden="true">
    <path v-if="area" :d="areaPath" :fill="color" opacity="0.14" />
    <polyline :points="pts" :stroke="color" fill="none" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
  </svg>
</template>

<style scoped>
.spark { width: 100%; height: 100%; display: block; }
</style>
