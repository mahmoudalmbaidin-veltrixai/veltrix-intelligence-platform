<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ name: string; color?: string; size?: number }>(), { size: 28 })
const initials = computed(() =>
  props.name
    .split(' ')
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase() ?? '')
    .join(''),
)
</script>

<template>
  <span
    class="vip-avatar"
    :style="{
      width: `${size}px`,
      height: `${size}px`,
      background: color ?? 'var(--vip-brand-500)',
      fontSize: `${Math.round(size * 0.4)}px`,
    }"
    :title="name"
  >{{ initials }}</span>
</template>

<style scoped>
.vip-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
  font-weight: var(--vip-fw-semibold);
  flex: none;
  user-select: none;
}
</style>
