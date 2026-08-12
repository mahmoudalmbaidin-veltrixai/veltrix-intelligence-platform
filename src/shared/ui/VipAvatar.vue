<script setup lang="ts">
import { computed, ref, watch } from 'vue'
const props = withDefaults(defineProps<{ name: string; color?: string; size?: number; src?: string | null }>(), {
  size: 28,
})
const initials = computed(() =>
  props.name
    .split(' ')
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase() ?? '')
    .join(''),
)
// Fall back to initials if the image fails to load.
const failed = ref(false)
watch(
  () => props.src,
  () => {
    failed.value = false
  },
)
const showImage = computed(() => !!props.src && !failed.value)
</script>

<template>
  <span
    class="vip-avatar"
    :style="{
      width: `${size}px`,
      height: `${size}px`,
      background: showImage ? 'transparent' : (color ?? 'var(--vip-brand-500)'),
      fontSize: `${Math.round(size * 0.4)}px`,
    }"
    :title="name"
  >
    <img v-if="showImage" :src="src ?? ''" :alt="name" class="vip-avatar__img" @error="failed = true" />
    <template v-else>{{ initials }}</template>
  </span>
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
  overflow: hidden;
}
.vip-avatar__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
}
</style>
