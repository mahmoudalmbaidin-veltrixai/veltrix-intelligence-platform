<script setup lang="ts">
/**
 * Schema-aware rename mapping for the Rename Columns node.
 * Rows map an upstream column (chosen from node.inputSchema) to a new name.
 * The persisted value is config.renames: Record<current, new> — unchanged
 * contract — so backend execution and save/reload are unaffected.
 */
import { computed, ref, watch } from 'vue'
import type { SchemaColumn } from '@/shared/types/pipeline'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const props = defineProps<{
  available: SchemaColumn[]
  modelValue: Record<string, string>
}>()
const emit = defineEmits<{ 'update:modelValue': [Record<string, string>] }>()

interface Row {
  from: string
  to: string
}
const rows = ref<Row[]>([])

// Hydrate local rows from the persisted map whenever the selected node changes.
watch(
  () => props.modelValue,
  (map) => {
    const entries = Object.entries(map ?? {})
    rows.value = entries.length ? entries.map(([from, to]) => ({ from, to })) : [{ from: '', to: '' }]
  },
  { immediate: true, deep: false },
)

const typeOf = (name: string) => props.available.find((c) => c.name === name)?.dataType ?? ''
const INVALID = /[^A-Za-z0-9_]/
const usedFrom = computed(() => rows.value.filter((r) => r.from).map((r) => r.from))

function rowError(row: Row, index: number): string | null {
  if (!row.from) return null
  if (!row.to.trim()) return 'New name is required.'
  if (INVALID.test(row.to)) return 'Only letters, numbers and underscore are allowed.'
  // duplicate source
  if (usedFrom.value.filter((f) => f === row.from).length > 1) return 'This column is mapped more than once.'
  // output-name collision with another mapping's target
  const targets = rows.value.filter((_, i) => i !== index && rows.value[i].from).map((r) => r.to.trim())
  if (targets.includes(row.to.trim())) return 'Another mapping already produces this name.'
  // collision with an untouched upstream column
  const renamedSources = new Set(usedFrom.value)
  const untouched = props.available.map((c) => c.name).filter((n) => !renamedSources.has(n))
  if (untouched.includes(row.to.trim())) return 'This name collides with an existing column.'
  return null
}

const anyError = computed(() => rows.value.some((r, i) => rowError(r, i) !== null))

function commit() {
  if (anyError.value) return
  const map: Record<string, string> = {}
  rows.value.forEach((r) => {
    if (r.from && r.to.trim() && r.to.trim() !== r.from) map[r.from] = r.to.trim()
  })
  emit('update:modelValue', map)
}

function addRow() {
  rows.value.push({ from: '', to: '' })
}
function removeRow(index: number) {
  rows.value.splice(index, 1)
  if (!rows.value.length) rows.value.push({ from: '', to: '' })
  commit()
}

// Bulk prefix / suffix applied to every mapped row's target.
const bulk = ref({ prefix: '', suffix: '' })
function applyBulk() {
  rows.value.forEach((r) => {
    if (r.from) r.to = `${bulk.value.prefix}${r.to || r.from}${bulk.value.suffix}`
  })
  commit()
}

const preview = computed(() => {
  const map = new Map(rows.value.filter((r) => r.from && r.to.trim()).map((r) => [r.from, r.to.trim()]))
  return props.available.map((c) => ({ from: c.name, to: map.get(c.name) ?? c.name, changed: map.has(c.name) }))
})
</script>

<template>
  <div class="rn">
    <div v-if="!available.length" class="rn__empty">
      <VipIcon name="info" :size="14" />
      <span>Connect an upstream node to load its columns.</span>
    </div>

    <template v-else>
      <table class="rn__table">
        <thead>
          <tr>
            <th>Current column</th>
            <th>New name</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in rows" :key="i">
            <td>
              <select v-model="row.from" class="rn__select" aria-label="Current column" @change="commit">
                <option value="">Select column…</option>
                <option v-for="c in available" :key="c.name" :value="c.name">{{ c.name }}</option>
              </select>
              <VipBadge v-if="row.from" tone="neutral" size="sm">{{ typeOf(row.from) }}</VipBadge>
            </td>
            <td>
              <input
                v-model="row.to"
                class="rn__input"
                :class="{ 'is-invalid': rowError(row, i) }"
                placeholder="new_name"
                aria-label="New name"
                @input="commit"
              />
              <span v-if="rowError(row, i)" class="rn__err">{{ rowError(row, i) }}</span>
            </td>
            <td>
              <button class="rn__del" aria-label="Remove mapping" @click="removeRow(i)">
                <VipIcon name="close" :size="12" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <button class="rn__add" @click="addRow"><VipIcon name="plus" :size="12" /> Add mapping</button>

      <div class="rn__bulk">
        <input v-model="bulk.prefix" class="rn__bulk-input" placeholder="prefix_" aria-label="Bulk prefix" />
        <input v-model="bulk.suffix" class="rn__bulk-input" placeholder="_suffix" aria-label="Bulk suffix" />
        <button @click="applyBulk">Apply to mapped</button>
      </div>

      <div class="rn__preview">
        <div class="rn__preview-title">Output schema preview</div>
        <ul>
          <li v-for="p in preview" :key="p.from" :class="{ 'is-changed': p.changed }">
            <span class="rn__mono">{{ p.from }}</span>
            <template v-if="p.changed"> <VipIcon name="chevronRight" :size="11" /> <span class="rn__mono">{{ p.to }}</span></template>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<style scoped>
.rn {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.rn__empty {
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
.rn__table {
  width: 100%;
  border-collapse: collapse;
}
.rn__table th {
  text-align: left;
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  font-weight: var(--vip-fw-medium);
  padding-bottom: var(--vip-sp-2);
}
.rn__table td {
  padding: var(--vip-sp-2) var(--vip-sp-2) var(--vip-sp-2) 0;
  vertical-align: top;
}
.rn__select,
.rn__input {
  width: 100%;
  height: 30px;
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  padding: 0 var(--vip-sp-3);
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-sm);
  outline: none;
}
.rn__input.is-invalid {
  border-color: var(--vip-danger);
}
.rn__input:focus,
.rn__select:focus {
  border-color: var(--vip-brand-500);
}
.rn__err {
  display: block;
  margin-top: 2px;
  font-size: var(--vip-fs-xs);
  color: var(--vip-danger-text);
}
.rn__del {
  width: 26px;
  height: 30px;
  background: none;
  border: none;
  color: var(--vip-text-muted);
  border-radius: var(--vip-radius-sm);
  cursor: pointer;
}
.rn__del:hover {
  background: var(--vip-danger-soft);
  color: var(--vip-danger-text);
}
.rn__add {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  background: none;
  border: 1px dashed var(--vip-border-strong);
  border-radius: var(--vip-radius-sm);
  padding: var(--vip-sp-2) var(--vip-sp-4);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-xs);
  cursor: pointer;
}
.rn__add:hover {
  border-color: var(--vip-brand-500);
  color: var(--vip-brand-text);
}
.rn__bulk {
  display: flex;
  gap: var(--vip-sp-3);
}
.rn__bulk-input {
  flex: 1;
  min-width: 0;
  height: 28px;
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  padding: 0 var(--vip-sp-3);
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-xs);
  outline: none;
}
.rn__bulk button {
  background: none;
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  padding: 0 var(--vip-sp-4);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-xs);
  cursor: pointer;
}
.rn__preview {
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  padding: var(--vip-sp-4);
}
.rn__preview-title {
  font-size: var(--vip-fs-xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
  margin-bottom: var(--vip-sp-3);
}
.rn__preview ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.rn__preview li {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.rn__preview li.is-changed {
  color: var(--vip-text-primary);
}
.rn__mono {
  font-family: var(--vip-font-mono);
}
</style>
