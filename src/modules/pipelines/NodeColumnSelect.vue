<script setup lang="ts">
/**
 * Schema-aware column selector for the Select Columns node.
 * Renders the real upstream columns (node.inputSchema) as a searchable,
 * checkable list. The persisted value is always the KEPT column list
 * (config.columns: string[]) so the backend contract is unchanged.
 */
import { computed, ref } from 'vue'
import type { SchemaColumn } from '@/shared/types/pipeline'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const props = defineProps<{
  available: SchemaColumn[]
  /** Currently kept column names (the persisted config.columns). */
  modelValue: string[]
}>()
const emit = defineEmits<{ 'update:modelValue': [string[]] }>()

const search = ref('')
// Authoring convenience only (not persisted): interpret checks as keep or remove.
const mode = ref<'keep' | 'remove'>('keep')

const kept = computed(() => new Set(props.modelValue ?? []))

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.available
  return props.available.filter((c) => c.name.toLowerCase().includes(q))
})

/** A column is "checked" = kept in keep-mode, or dropped in remove-mode. */
function isChecked(name: string): boolean {
  return mode.value === 'keep' ? kept.value.has(name) : !kept.value.has(name)
}

function emitKept(next: Set<string>) {
  // Preserve upstream ordering for a stable, predictable output schema.
  emit(
    'update:modelValue',
    props.available.filter((c) => next.has(c.name)).map((c) => c.name),
  )
}

function toggle(name: string) {
  const next = new Set(kept.value)
  const willKeep = mode.value === 'keep' ? !isChecked(name) : isChecked(name)
  if (willKeep) next.add(name)
  else next.delete(name)
  emitKept(next)
}

function selectAll() {
  emitKept(new Set(props.available.map((c) => c.name)))
}
function clearAll() {
  emitKept(new Set())
}
function invert() {
  const next = new Set<string>()
  props.available.forEach((c) => {
    if (!kept.value.has(c.name)) next.add(c.name)
  })
  emitKept(next)
}

const keptCount = computed(() => props.available.filter((c) => kept.value.has(c.name)).length)
const total = computed(() => props.available.length)
const zeroKept = computed(() => total.value > 0 && keptCount.value === 0)
// A previously selected column that no longer exists upstream (schema drift).
const staleSelections = computed(() => {
  const names = new Set(props.available.map((c) => c.name))
  return (props.modelValue ?? []).filter((n) => !names.has(n))
})
</script>

<template>
  <div class="cols">
    <div v-if="!available.length" class="cols__empty">
      <VipIcon name="info" :size="14" />
      <span>Connect an upstream node to load its columns.</span>
    </div>

    <template v-else>
      <div class="cols__toolbar">
        <div class="cols__search">
          <VipIcon name="search" :size="13" />
          <input
            v-model="search"
            class="cols__search-input"
            placeholder="Search columns…"
            aria-label="Search columns"
          />
        </div>
        <div class="cols__mode" role="group" aria-label="Selection mode">
          <button :class="{ 'is-active': mode === 'keep' }" @click="mode = 'keep'">Keep</button>
          <button :class="{ 'is-active': mode === 'remove' }" @click="mode = 'remove'">Remove</button>
        </div>
      </div>

      <div class="cols__actions">
        <button @click="selectAll">Select all</button>
        <button @click="clearAll">Clear</button>
        <button @click="invert">Invert</button>
        <span class="cols__count">{{ keptCount }} / {{ total }} kept</span>
      </div>

      <ul class="cols__list">
        <li v-for="col in filtered" :key="col.name" class="cols__item">
          <label class="cols__row">
            <input
              type="checkbox"
              :checked="isChecked(col.name)"
              :aria-label="`${mode === 'keep' ? 'Keep' : 'Remove'} ${col.name}`"
              @change="toggle(col.name)"
            />
            <span class="cols__name">{{ col.name }}</span>
            <VipBadge tone="neutral" size="sm">{{ col.dataType }}</VipBadge>
          </label>
        </li>
        <li v-if="!filtered.length" class="cols__none">No columns match “{{ search }}”.</li>
      </ul>

      <p v-if="zeroKept" class="cols__warn" role="alert">
        <VipIcon name="warning" :size="13" /> No columns are kept — downstream nodes will receive an empty schema.
      </p>
      <p v-if="staleSelections.length" class="cols__warn" role="alert">
        <VipIcon name="warning" :size="13" /> {{ staleSelections.length }} selected column(s) no longer exist upstream:
        {{ staleSelections.join(', ') }}
      </p>
      <p class="cols__hint">
        {{
          mode === 'keep'
            ? 'Checked columns continue to the next node.'
            : 'Checked columns are dropped; the rest continue.'
        }}
      </p>
    </template>
  </div>
</template>

<style scoped>
.cols {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.cols__empty {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  padding: var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px dashed var(--vip-border);
  border-radius: var(--vip-radius-md);
}
.cols__toolbar {
  display: flex;
  gap: var(--vip-sp-3);
  align-items: center;
}
.cols__search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  height: 30px;
  padding: 0 var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
}
.cols__search-input {
  flex: 1;
  min-width: 0;
  background: none;
  border: none;
  outline: none;
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-sm);
}
.cols__mode {
  display: inline-flex;
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  overflow: hidden;
}
.cols__mode button {
  padding: var(--vip-sp-2) var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: none;
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-xs);
  cursor: pointer;
}
.cols__mode button.is-active {
  background: var(--vip-brand-500);
  color: var(--vip-on-brand, #fff);
}
.cols__actions {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
}
.cols__actions button {
  background: none;
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  padding: var(--vip-sp-1) var(--vip-sp-3);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-xs);
  cursor: pointer;
}
.cols__actions button:hover {
  border-color: var(--vip-brand-500);
  color: var(--vip-brand-text);
}
.cols__count {
  margin-left: auto;
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.cols__list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 280px;
  overflow-y: auto;
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
}
.cols__item + .cols__item {
  border-top: 1px solid var(--vip-border-subtle);
}
.cols__row {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  cursor: pointer;
}
.cols__row:hover {
  background: var(--vip-surface-2);
}
.cols__name {
  flex: 1;
  min-width: 0;
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-primary);
  overflow-wrap: anywhere;
}
.cols__none {
  padding: var(--vip-sp-4);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.cols__warn {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-xs);
  color: var(--vip-warning-text);
}
.cols__hint {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
</style>
