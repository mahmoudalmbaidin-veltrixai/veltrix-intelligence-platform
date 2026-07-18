<script setup lang="ts">
import { useId } from 'vue'

interface Opt {
  value: string
  label: string
}
const props = defineProps<{
  modelValue?: string
  options: Opt[]
  label?: string
  placeholder?: string
  error?: string
  help?: string
  required?: boolean
  disabled?: boolean
  size?: 'sm' | 'md'
}>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const id = useId()
</script>

<template>
  <div class="vip-field">
    <label v-if="label" :for="id" class="vip-field__label">
      {{ label }}<span v-if="required" class="vip-field__req">*</span>
    </label>
    <div
      class="vip-select"
      :class="[`vip-select--${props.size ?? 'md'}`, { 'is-error': error, 'is-disabled': disabled }]"
    >
      <select
        :id="id"
        class="vip-select__el"
        :value="modelValue"
        :disabled="disabled"
        @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
      >
        <option v-if="placeholder" value="" disabled :selected="!modelValue">{{ placeholder }}</option>
        <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <svg
        class="vip-select__chev"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </div>
    <p v-if="error" class="vip-field__msg is-error">{{ error }}</p>
    <p v-else-if="help" class="vip-field__msg">{{ help }}</p>
  </div>
</template>

<style scoped>
.vip-field {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.vip-field__label {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-secondary);
}
.vip-field__req {
  color: var(--vip-danger);
  margin-left: 3px;
}
.vip-select {
  position: relative;
  display: flex;
  align-items: center;
}
.vip-select__el {
  appearance: none;
  width: 100%;
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  padding: 0 var(--vip-sp-8) 0 var(--vip-sp-5);
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
  outline: none;
  cursor: pointer;
}
.vip-select--sm .vip-select__el {
  height: 28px;
}
.vip-select--md .vip-select__el {
  height: 34px;
}
.vip-select__el:focus {
  border-color: var(--vip-brand-500);
  box-shadow: 0 0 0 3px var(--vip-brand-soft);
}
.vip-select.is-error .vip-select__el {
  border-color: var(--vip-danger);
}
.vip-select.is-disabled {
  opacity: 0.55;
  pointer-events: none;
}
.vip-select__chev {
  position: absolute;
  right: var(--vip-sp-5);
  color: var(--vip-text-muted);
  pointer-events: none;
}
.vip-field__msg {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.vip-field__msg.is-error {
  color: var(--vip-danger-text);
}
</style>
