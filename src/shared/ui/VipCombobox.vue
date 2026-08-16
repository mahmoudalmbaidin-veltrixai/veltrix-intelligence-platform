<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import VipIcon from './VipIcon.vue'

interface Opt {
  value: string
  label: string
}
const props = withDefaults(
  defineProps<{
    modelValue?: string
    options: Opt[]
    label?: string
    ariaLabel?: string
    placeholder?: string
    help?: string
    error?: string
    required?: boolean
    disabled?: boolean
    size?: 'sm' | 'md'
    /** Cap on rendered results so the menu never mounts thousands of nodes. */
    maxResults?: number
  }>(),
  { size: 'md', maxResults: 50 },
)
const emit = defineEmits<{ 'update:modelValue': [string] }>()

const id = useId()
const listId = `${id}-list`
const descId = `${id}-desc`
const root = ref<HTMLElement>()

const open = ref(false)
const query = ref('')
const activeIndex = ref(0)

const selectedLabel = computed(
  () => props.options.find((o) => o.value === props.modelValue)?.label ?? props.modelValue ?? '',
)

// Fold case, underscores and slashes so "New York", "asia/", "Asia Riyadh"
// all match "America/New_York" / "Asia/Riyadh".
function norm(value: string): string {
  return value.toLowerCase().replace(/[_/]+/g, ' ').replace(/\s+/g, ' ').trim()
}

const filtered = computed<Opt[]>(() => {
  const q = norm(query.value)
  if (!q) {
    // No query: surface the current selection first so it is always visible
    // even when it would fall outside the capped head of the list.
    const selected = props.options.find((o) => o.value === props.modelValue)
    const rest = selected ? props.options.filter((o) => o.value !== props.modelValue) : props.options
    return selected ? [selected, ...rest] : props.options.slice()
  }
  return props.options.filter((o) => norm(`${o.value} ${o.label}`).includes(q))
})

const truncated = computed(() => filtered.value.length > props.maxResults)
const visible = computed(() => filtered.value.slice(0, props.maxResults))
const optionId = (index: number) => `${listId}-opt-${index}`

function openMenu() {
  if (props.disabled || open.value) return
  open.value = true
  query.value = ''
  const idx = visible.value.findIndex((o) => o.value === props.modelValue)
  activeIndex.value = idx >= 0 ? idx : 0
}

function closeMenu() {
  open.value = false
  query.value = ''
}

function select(option: Opt) {
  emit('update:modelValue', option.value)
  closeMenu()
}

function onInput(event: Event) {
  open.value = true
  query.value = (event.target as HTMLInputElement).value
  activeIndex.value = 0
}

function move(delta: number) {
  if (!open.value) {
    openMenu()
    return
  }
  const count = visible.value.length
  if (count === 0) return
  activeIndex.value = Math.min(Math.max(activeIndex.value + delta, 0), count - 1)
}

function onKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      move(1)
      break
    case 'ArrowUp':
      event.preventDefault()
      move(-1)
      break
    case 'Enter':
      if (open.value && visible.value[activeIndex.value]) {
        event.preventDefault()
        select(visible.value[activeIndex.value])
      }
      break
    case 'Escape':
      if (open.value) {
        event.preventDefault()
        closeMenu()
      }
      break
    case 'Home':
      if (open.value) {
        event.preventDefault()
        activeIndex.value = 0
      }
      break
    case 'End':
      if (open.value) {
        event.preventDefault()
        activeIndex.value = Math.max(visible.value.length - 1, 0)
      }
      break
  }
}

// Keep the active row scrolled into view as the user arrows through results.
watch(activeIndex, async () => {
  if (!open.value) return
  await nextTick()
  const el = document.getElementById(optionId(activeIndex.value))
  el?.scrollIntoView?.({ block: 'nearest' })
})

function onDocPointer(event: MouseEvent) {
  if (open.value && root.value && !root.value.contains(event.target as Node)) closeMenu()
}
onMounted(() => document.addEventListener('mousedown', onDocPointer))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocPointer))
</script>

<template>
  <div ref="root" class="vip-field">
    <label v-if="label" :for="id" class="vip-field__label">
      {{ label }}<span v-if="required" class="vip-field__req" aria-hidden="true">*</span>
    </label>
    <div
      class="vip-combobox"
      :class="[`vip-combobox--${size}`, { 'is-open': open, 'is-error': error, 'is-disabled': disabled }]"
    >
      <div class="vip-combobox__control">
        <VipIcon name="search" :size="15" class="vip-combobox__icon" />
        <input
          :id="id"
          class="vip-combobox__input"
          type="text"
          role="combobox"
          autocomplete="off"
          spellcheck="false"
          :value="open ? query : selectedLabel"
          :placeholder="placeholder ?? 'Search…'"
          :disabled="disabled"
          :aria-label="label ? undefined : (ariaLabel ?? placeholder ?? 'Search')"
          :aria-expanded="open"
          aria-haspopup="listbox"
          aria-autocomplete="list"
          :aria-controls="listId"
          :aria-activedescendant="open && visible.length ? optionId(activeIndex) : undefined"
          :aria-invalid="!!error"
          :aria-describedby="error || help ? descId : undefined"
          @focus="openMenu"
          @input="onInput"
          @keydown="onKeydown"
        />
        <svg
          class="vip-combobox__chev"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </div>
      <ul v-if="open" :id="listId" class="vip-combobox__menu" role="listbox">
        <li
          v-for="(o, i) in visible"
          :id="optionId(i)"
          :key="o.value"
          class="vip-combobox__opt"
          :class="{ 'is-active': i === activeIndex, 'is-selected': o.value === modelValue }"
          role="option"
          :aria-selected="o.value === modelValue"
          @mousedown.prevent
          @click="select(o)"
          @mousemove="activeIndex = i"
        >
          <span class="vip-combobox__opt-label">{{ o.label }}</span>
          <VipIcon v-if="o.value === modelValue" name="check" :size="14" class="vip-combobox__opt-check" />
        </li>
        <li v-if="visible.length === 0" class="vip-combobox__empty" role="presentation">No matches</li>
        <li v-else-if="truncated" class="vip-combobox__more" role="presentation">
          Showing first {{ maxResults }} — keep typing to narrow…
        </li>
      </ul>
    </div>
    <p v-if="error" :id="descId" class="vip-field__msg is-error" role="alert">{{ error }}</p>
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
}
.vip-field__req {
  color: var(--vip-danger);
  margin-left: 3px;
}
.vip-combobox {
  position: relative;
}
.vip-combobox__control {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  padding: 0 var(--vip-sp-5);
}
.vip-combobox--sm .vip-combobox__control {
  height: 28px;
}
.vip-combobox--md .vip-combobox__control {
  height: 34px;
}
.vip-combobox__control:focus-within {
  border-color: var(--vip-brand-500);
  box-shadow: 0 0 0 3px var(--vip-brand-soft);
}
.vip-combobox.is-error .vip-combobox__control {
  border-color: var(--vip-danger);
}
.vip-combobox.is-disabled {
  opacity: 0.55;
  pointer-events: none;
}
.vip-combobox__icon {
  color: var(--vip-text-muted);
  flex: none;
}
.vip-combobox__input {
  flex: 1;
  min-width: 0;
  background: none;
  border: none;
  outline: none;
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
}
.vip-combobox__input::placeholder {
  color: var(--vip-text-disabled);
}
.vip-combobox__chev {
  color: var(--vip-text-muted);
  flex: none;
}
.vip-combobox__menu {
  position: absolute;
  z-index: 40;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  max-height: 260px;
  overflow-y: auto;
  margin: 0;
  padding: var(--vip-sp-2);
  list-style: none;
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  box-shadow: var(--vip-shadow-lg, 0 12px 32px rgba(0, 0, 0, 0.24));
}
.vip-combobox__opt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  border-radius: var(--vip-radius-sm);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-primary);
  cursor: pointer;
}
.vip-combobox__opt.is-active {
  background: var(--vip-surface-hover);
}
.vip-combobox__opt.is-selected {
  color: var(--vip-brand-text);
  font-weight: var(--vip-fw-medium);
}
.vip-combobox__opt-check {
  color: var(--vip-brand-500);
  flex: none;
}
.vip-combobox__empty,
.vip-combobox__more {
  padding: var(--vip-sp-3) var(--vip-sp-4);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.vip-field__msg {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.vip-field__msg.is-error {
  color: var(--vip-danger-text);
}
</style>
