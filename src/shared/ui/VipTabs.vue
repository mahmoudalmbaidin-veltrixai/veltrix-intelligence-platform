<script setup lang="ts">
import VipBadge from './VipBadge.vue'
interface Tab {
  value: string
  label: string
  count?: number
}
defineProps<{ modelValue: string; tabs: Tab[] }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
</script>

<template>
  <div class="vip-tabs" role="tablist">
    <button
      v-for="t in tabs"
      :key="t.value"
      type="button"
      role="tab"
      :aria-selected="modelValue === t.value"
      class="vip-tabs__tab"
      :class="{ 'is-active': modelValue === t.value }"
      @click="emit('update:modelValue', t.value)"
    >
      {{ t.label }}
      <VipBadge v-if="t.count != null" size="sm" tone="neutral">{{ t.count }}</VipBadge>
    </button>
  </div>
</template>

<style scoped>
.vip-tabs {
  display: flex;
  gap: var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border);
}
.vip-tabs__tab {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
  background: none;
  border: none;
  padding: var(--vip-sp-4) 0;
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition:
    color var(--vip-motion-fast),
    border-color var(--vip-motion-fast);
}
.vip-tabs__tab:hover {
  color: var(--vip-text-primary);
}
.vip-tabs__tab.is-active {
  color: var(--vip-text-primary);
  border-bottom-color: var(--vip-brand-500);
}
</style>
