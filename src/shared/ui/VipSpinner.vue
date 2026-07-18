<script setup lang="ts">
withDefaults(defineProps<{ size?: number; label?: string }>(), { size: 18 })
</script>

<template>
  <span class="vip-spinner-wrap" role="status">
    <span class="vip-spinner" :style="{ width: `${size}px`, height: `${size}px` }" />
    <span v-if="label" class="vip-spinner-label">{{ label }}</span>
  </span>
</template>

<style scoped>
.vip-spinner-wrap {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-4);
  color: var(--vip-text-muted);
}
.vip-spinner {
  border: 2px solid var(--vip-border-strong);
  border-right-color: var(--vip-brand-500);
  border-radius: 50%;
  animation: vip-spin 0.7s linear infinite;
}
.vip-spinner-label {
  font-size: var(--vip-fs-sm);
}
@keyframes vip-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
