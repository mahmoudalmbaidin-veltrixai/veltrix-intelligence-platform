<script setup lang="ts">
import { computed } from 'vue'
import { schemeColor } from './colors'

const props = defineProps<{ points: { x: number; y: number; size?: number; label?: string }[]; scheme?: string }>()
const W = 640
const H = 320
const PAD = 44
const maxX = computed(() => Math.max(1, ...props.points.map((p) => p.x)))
const maxY = computed(() => Math.max(1, ...props.points.map((p) => p.y)))
const maxS = computed(() => Math.max(1, ...props.points.map((p) => p.size ?? 1)))
function cx(x: number) { return PAD + (x / maxX.value) * (W - PAD * 1.5) }
function cy(y: number) { return H - PAD - (y / maxY.value) * (H - PAD * 1.5) }
function r(s?: number) { return 4 + ((s ?? 1) / maxS.value) * 14 }
</script>

<template>
  <svg :viewBox="`0 0 ${W} ${H}`" class="scatter" role="img">
    <line :x1="PAD" :y1="H - PAD" :x2="W - PAD / 2" :y2="H - PAD" class="scatter__axis" />
    <line :x1="PAD" :y1="PAD / 2" :x2="PAD" :y2="H - PAD" class="scatter__axis" />
    <circle
      v-for="(p, i) in points"
      :key="i"
      :cx="cx(p.x)"
      :cy="cy(p.y)"
      :r="r(p.size)"
      :fill="schemeColor(scheme, i)"
      class="scatter__pt"
    >
      <title v-if="p.label">{{ p.label }}</title>
    </circle>
  </svg>
</template>

<style scoped>
.scatter { width: 100%; height: 100%; }
.scatter__axis { stroke: var(--vip-border); stroke-width: 1; }
.scatter__pt { opacity: 0.7; transition: opacity var(--vip-motion-fast); }
.scatter__pt:hover { opacity: 1; }
</style>
