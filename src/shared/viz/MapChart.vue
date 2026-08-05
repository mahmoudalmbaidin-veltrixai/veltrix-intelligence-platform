<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ points: { x: number; y: number; size: number; label?: string }[] }>()
const width = 640
const height = 300
const pad = 20
const plotted = computed(() =>
  props.points.map((point) => ({
    ...point,
    px: pad + ((Math.max(-180, Math.min(180, point.x)) + 180) / 360) * (width - pad * 2),
    py: pad + ((90 - Math.max(-90, Math.min(90, point.y))) / 180) * (height - pad * 2),
    radius: Math.max(4, Math.min(14, Math.sqrt(Math.abs(point.size || 1)))),
  })),
)
</script>

<template>
  <svg :viewBox="`0 0 ${width} ${height}`" class="map" role="img" aria-label="Geospatial data map">
    <rect :x="pad" :y="pad" :width="width - pad * 2" :height="height - pad * 2" class="map__ocean" />
    <path
      class="map__land"
      d="M55 92 88 60 145 55 188 78 173 111 132 118 108 151 73 139ZM214 54 270 40 322 63 343 102 318 128 282 117 260 84ZM354 72 418 50 484 64 548 91 528 126 469 136 430 116 386 125ZM390 155 443 143 481 167 463 220 421 242 386 212ZM518 180 558 166 591 193 571 226 531 218Z"
    />
    <g class="map__grid">
      <line v-for="x in [120, 220, 320, 420, 520]" :key="`x-${x}`" :x1="x" :x2="x" :y1="pad" :y2="height - pad" />
      <line v-for="y in [75, 150, 225]" :key="`y-${y}`" :x1="pad" :x2="width - pad" :y1="y" :y2="y" />
    </g>
    <circle
      v-for="(point, index) in plotted"
      :key="`${point.label ?? 'point'}-${index}`"
      :cx="point.px"
      :cy="point.py"
      :r="point.radius"
      class="map__point"
    >
      <title>{{ point.label ?? `${point.y}, ${point.x}` }}</title>
    </circle>
  </svg>
</template>

<style scoped>
.map {
  width: 100%;
  height: 100%;
  min-height: 160px;
}
.map__ocean {
  fill: var(--color-surface-subtle, #eff6ff);
  stroke: var(--color-border, #cbd5e1);
}
.map__land {
  fill: var(--color-surface-muted, #cbd5e1);
  stroke: var(--color-border-strong, #94a3b8);
  stroke-width: 1.5;
}
.map__grid line {
  stroke: var(--color-border, #cbd5e1);
  stroke-width: 0.6;
  stroke-dasharray: 3 4;
}
.map__point {
  fill: var(--color-primary, #2563eb);
  fill-opacity: 0.78;
  stroke: white;
  stroke-width: 2;
}
</style>
