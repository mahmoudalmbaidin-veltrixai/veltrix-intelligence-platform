<script setup lang="ts">
const props = defineProps<{ modelValue?: boolean; label?: string; disabled?: boolean; size?: 'sm' | 'md' }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()
</script>

<template>
  <label class="vip-switch" :class="[`vip-switch--${props.size ?? 'md'}`, { 'is-disabled': disabled }]">
    <button
      type="button"
      role="switch"
      :aria-checked="!!modelValue"
      class="vip-switch__track"
      :class="{ 'is-on': modelValue }"
      :disabled="disabled"
      @click="emit('update:modelValue', !modelValue)"
    >
      <span class="vip-switch__thumb" />
    </button>
    <span v-if="label" class="vip-switch__label">{{ label }}</span>
  </label>
</template>

<style scoped>
.vip-switch { display: inline-flex; align-items: center; gap: var(--vip-sp-4); cursor: pointer; }
.vip-switch.is-disabled { opacity: 0.5; cursor: not-allowed; }
.vip-switch__track {
  position: relative;
  background: var(--vip-surface-active);
  border: 1px solid var(--vip-border-strong);
  border-radius: var(--vip-radius-full);
  transition: background var(--vip-motion-fast), border-color var(--vip-motion-fast);
  padding: 0;
}
.vip-switch--md .vip-switch__track { width: 34px; height: 20px; }
.vip-switch--sm .vip-switch__track { width: 28px; height: 16px; }
.vip-switch__track.is-on { background: var(--vip-brand-500); border-color: var(--vip-brand-500); }
.vip-switch__thumb {
  position: absolute;
  top: 50%;
  left: 2px;
  transform: translateY(-50%);
  background: #fff;
  border-radius: 50%;
  transition: left var(--vip-motion-fast) var(--vip-ease-standard);
}
.vip-switch--md .vip-switch__thumb { width: 14px; height: 14px; }
.vip-switch--sm .vip-switch__thumb { width: 11px; height: 11px; }
.vip-switch--md .vip-switch__track.is-on .vip-switch__thumb { left: 16px; }
.vip-switch--sm .vip-switch__track.is-on .vip-switch__thumb { left: 13px; }
.vip-switch__label { font-size: var(--vip-fs-md); color: var(--vip-text-secondary); }
</style>
