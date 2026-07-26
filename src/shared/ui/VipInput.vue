<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import VipIcon from './VipIcon.vue'

const props = withDefaults(
  defineProps<{
    modelValue?: string | number | null
    label?: string
    description?: string
    placeholder?: string
    type?: string
    icon?: string
    error?: string
    warning?: string
    help?: string
    required?: boolean
    disabled?: boolean
    readonly?: boolean
    prefix?: string
    suffix?: string
    size?: 'sm' | 'md'
    /** Native autocomplete hint for password managers (e.g. "current-password"). */
    autocomplete?: string
    /** Native form field name — helps password managers map fields. */
    name?: string
    autofocus?: boolean
    inputmode?: 'text' | 'email' | 'numeric' | 'tel' | 'url' | 'search'
  }>(),
  { type: 'text', size: 'md' },
)

const emit = defineEmits<{
  'update:modelValue': [string | number]
  enter: []
  keydown: [KeyboardEvent]
  keyup: [KeyboardEvent]
}>()
const id = useId()
const descId = computed(() => `${id}-desc`)
const inputEl = ref<HTMLInputElement>()

function onInput(e: Event) {
  const el = e.target as HTMLInputElement
  emit('update:modelValue', props.type === 'number' ? Number(el.value) : el.value)
}

// Exposed so callers can manage focus (e.g. keeping the caret when toggling
// password visibility) without reaching into internals.
defineExpose({
  focus: () => inputEl.value?.focus(),
  el: inputEl,
})
</script>

<template>
  <div class="vip-field" :class="{ 'is-error': error }">
    <label v-if="label" :for="id" class="vip-field__label">
      {{ label }}
      <span v-if="required" class="vip-field__req" aria-hidden="true">*</span>
      <span v-else-if="!required && label" class="vip-field__opt">optional</span>
    </label>
    <p v-if="description" class="vip-field__desc">{{ description }}</p>
    <div
      class="vip-input"
      :class="[
        `vip-input--${size}`,
        { 'is-error': error, 'is-warning': warning, 'is-disabled': disabled, 'is-readonly': readonly },
      ]"
    >
      <VipIcon v-if="icon" :name="icon" :size="15" class="vip-input__icon" />
      <span v-if="prefix" class="vip-input__affix">{{ prefix }}</span>
      <input
        :id="id"
        ref="inputEl"
        class="vip-input__el"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :required="required"
        :name="name"
        :autocomplete="autocomplete"
        :autofocus="autofocus"
        :inputmode="inputmode"
        :aria-invalid="!!error"
        :aria-describedby="error || help ? descId : undefined"
        @input="onInput"
        @keydown="emit('keydown', $event)"
        @keyup="emit('keyup', $event)"
        @keyup.enter="emit('enter')"
      />
      <span v-if="suffix" class="vip-input__affix">{{ suffix }}</span>
      <slot name="suffix" />
    </div>
    <p v-if="error" :id="descId" class="vip-field__msg is-error" role="alert">{{ error }}</p>
    <p v-else-if="warning" class="vip-field__msg is-warning">{{ warning }}</p>
    <p v-else-if="help" :id="descId" class="vip-field__msg">{{ help }}</p>
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
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
}
.vip-field__req {
  color: var(--vip-danger);
}
.vip-field__opt {
  color: var(--vip-text-muted);
  font-weight: var(--vip-fw-regular);
  font-size: var(--vip-fs-xs);
}
.vip-field__desc {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin-top: -2px;
}

.vip-input {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  padding: 0 var(--vip-sp-5);
  transition:
    border-color var(--vip-motion-fast),
    box-shadow var(--vip-motion-fast);
}
.vip-input--sm {
  height: 28px;
}
.vip-input--md {
  height: 34px;
}
.vip-input:focus-within {
  border-color: var(--vip-brand-500);
  box-shadow: 0 0 0 3px var(--vip-brand-soft);
}
.vip-input.is-error {
  border-color: var(--vip-danger);
}
.vip-input.is-error:focus-within {
  box-shadow: 0 0 0 3px var(--vip-danger-soft);
}
.vip-input.is-warning {
  border-color: var(--vip-warning);
}
.vip-input.is-disabled {
  opacity: 0.55;
  pointer-events: none;
}
.vip-input.is-readonly {
  background: var(--vip-surface-inset);
}
.vip-input__icon {
  color: var(--vip-text-muted);
  flex: none;
}
.vip-input__affix {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  flex: none;
}
.vip-input__el {
  flex: 1;
  min-width: 0;
  background: none;
  border: none;
  outline: none;
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
}
.vip-input__el::placeholder {
  color: var(--vip-text-disabled);
}

.vip-field__msg {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.vip-field__msg.is-error {
  color: var(--vip-danger-text);
}
.vip-field__msg.is-warning {
  color: var(--vip-warning-text);
}
</style>
