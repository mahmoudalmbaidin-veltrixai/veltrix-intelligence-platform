<script setup lang="ts" generic="T extends string">
import VipIcon from './VipIcon.vue'
defineProps<{
  modelValue: T
  options: { value: T; label?: string; icon?: string; title?: string }[]
  size?: 'sm' | 'md'
}>()
const emit = defineEmits<{ 'update:modelValue': [T] }>()
</script>

<template>
  <div class="vip-seg" :class="`vip-seg--${size ?? 'md'}`" role="tablist">
    <button
      v-for="o in options"
      :key="o.value"
      type="button"
      role="tab"
      :aria-selected="modelValue === o.value"
      class="vip-seg__btn"
      :class="{ 'is-active': modelValue === o.value }"
      :title="o.title ?? o.label"
      @click="emit('update:modelValue', o.value)"
    >
      <VipIcon v-if="o.icon" :name="o.icon" :size="14" />
      <span v-if="o.label">{{ o.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.vip-seg {
  display: inline-flex;
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  padding: 2px;
  gap: 2px;
}
.vip-seg__btn {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
  background: none;
  border: none;
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
  font-weight: var(--vip-fw-medium);
  transition:
    background var(--vip-motion-fast),
    color var(--vip-motion-fast);
}
.vip-seg--sm .vip-seg__btn {
  height: 24px;
  padding: 0 var(--vip-sp-4);
  font-size: var(--vip-fs-xs);
}
.vip-seg--md .vip-seg__btn {
  height: 28px;
  padding: 0 var(--vip-sp-5);
  font-size: var(--vip-fs-sm);
}
.vip-seg__btn:hover {
  color: var(--vip-text-primary);
}
.vip-seg__btn.is-active {
  background: var(--vip-surface-1);
  color: var(--vip-text-primary);
  box-shadow: var(--vip-shadow-sm);
}
</style>
