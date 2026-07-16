<script setup lang="ts">
import VipIcon from './VipIcon.vue'
defineProps<{ modelValue?: boolean; label?: string; indeterminate?: boolean; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()
</script>

<template>
  <label class="vip-check" :class="{ 'is-disabled': disabled }">
    <button
      type="button"
      role="checkbox"
      :aria-checked="indeterminate ? 'mixed' : !!modelValue"
      class="vip-check__box"
      :class="{ 'is-on': modelValue || indeterminate }"
      :disabled="disabled"
      @click="emit('update:modelValue', !modelValue)"
    >
      <VipIcon v-if="indeterminate" name="minus" :size="11" :stroke-width="3" />
      <VipIcon v-else-if="modelValue" name="check" :size="11" :stroke-width="3" />
    </button>
    <span v-if="label" class="vip-check__label">{{ label }}</span>
  </label>
</template>

<style scoped>
.vip-check { display: inline-flex; align-items: center; gap: var(--vip-sp-4); cursor: pointer; }
.vip-check.is-disabled { opacity: 0.5; cursor: not-allowed; }
.vip-check__box {
  width: 16px; height: 16px;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-strong);
  border-radius: var(--vip-radius-xs);
  color: #fff;
  padding: 0;
  transition: background var(--vip-motion-fast), border-color var(--vip-motion-fast);
}
.vip-check__box.is-on { background: var(--vip-brand-500); border-color: var(--vip-brand-500); }
.vip-check__label { font-size: var(--vip-fs-md); color: var(--vip-text-secondary); }
</style>
