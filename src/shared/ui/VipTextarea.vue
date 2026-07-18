<script setup lang="ts">
import { useId } from 'vue'

defineProps<{
  modelValue?: string
  label?: string
  placeholder?: string
  rows?: number
  error?: string
  help?: string
  required?: boolean
  mono?: boolean
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const id = useId()
</script>

<template>
  <div class="vip-field">
    <label v-if="label" :for="id" class="vip-field__label">
      {{ label }}<span v-if="required" class="vip-field__req">*</span>
    </label>
    <textarea
      :id="id"
      class="vip-textarea"
      :class="{ 'is-mono': mono, 'is-error': error }"
      :value="modelValue"
      :rows="rows ?? 4"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />
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
.vip-textarea {
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  padding: var(--vip-sp-4) var(--vip-sp-5);
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
  resize: vertical;
  outline: none;
}
.vip-textarea:focus {
  border-color: var(--vip-brand-500);
  box-shadow: 0 0 0 3px var(--vip-brand-soft);
}
.vip-textarea.is-mono {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
}
.vip-textarea.is-error {
  border-color: var(--vip-danger);
}
.vip-field__msg {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.vip-field__msg.is-error {
  color: var(--vip-danger-text);
}
</style>
