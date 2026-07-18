<script setup lang="ts">
withDefaults(defineProps<{ width?: string; height?: string; rounded?: boolean; block?: boolean }>(), {
  width: '100%',
  height: '14px',
})
</script>

<template>
  <span
    class="vip-skeleton"
    :class="{ 'is-rounded': rounded, 'is-block': block }"
    :style="{ width, height }"
    aria-hidden="true"
  />
</template>

<style scoped>
.vip-skeleton {
  display: inline-block;
  background: linear-gradient(90deg, var(--vip-surface-2) 25%, var(--vip-surface-3) 50%, var(--vip-surface-2) 75%);
  background-size: 200% 100%;
  border-radius: var(--vip-radius-sm);
  animation: vip-shimmer 1.3s infinite;
}
.is-rounded {
  border-radius: var(--vip-radius-full);
}
.is-block {
  display: block;
}
@keyframes vip-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
