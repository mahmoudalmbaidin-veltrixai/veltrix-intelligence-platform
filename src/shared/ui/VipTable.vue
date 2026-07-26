<script setup lang="ts" generic="T">
import { computed } from 'vue'
import VipIcon from './VipIcon.vue'
import VipCheckbox from './VipCheckbox.vue'
import VipSkeleton from './VipSkeleton.vue'
import VipEmptyState from './VipEmptyState.vue'

export interface Column<Row> {
  key: string
  label: string
  align?: 'left' | 'right' | 'center'
  width?: string
  sortable?: boolean
  cell?: (row: Row) => unknown
}

const props = withDefaults(
  defineProps<{
    columns: Column<T>[]
    rows: T[]
    rowKey: (row: T) => string
    loading?: boolean
    density?: 'comfortable' | 'compact'
    selectable?: boolean
    selected?: string[]
    sortKey?: string
    sortDir?: 'asc' | 'desc'
    emptyTitle?: string
    emptyDescription?: string
    clickable?: boolean
    skeletonRows?: number
  }>(),
  { density: 'comfortable', emptyTitle: 'No records', skeletonRows: 6 },
)

const emit = defineEmits<{
  'update:selected': [string[]]
  sort: [key: string]
  rowClick: [T]
}>()

const allSelected = computed(
  () => props.rows.length > 0 && props.rows.every((r) => props.selected?.includes(props.rowKey(r))),
)
const someSelected = computed(() => !!props.selected?.length && !allSelected.value)

function toggleAll() {
  if (allSelected.value) emit('update:selected', [])
  else emit('update:selected', props.rows.map(props.rowKey))
}
function toggleRow(row: T) {
  const key = props.rowKey(row)
  const set = new Set(props.selected ?? [])
  if (set.has(key)) set.delete(key)
  else set.add(key)
  emit('update:selected', [...set])
}
function cellValue(col: Column<T>, row: T): unknown {
  return col.cell ? col.cell(row) : (row as Record<string, unknown>)[col.key]
}
</script>

<template>
  <div class="vip-table-wrap">
    <table class="vip-table" :class="`is-${density}`">
      <thead>
        <tr>
          <th v-if="selectable" class="vip-table__check">
            <VipCheckbox :model-value="allSelected" :indeterminate="someSelected" @update:model-value="toggleAll" />
          </th>
          <th
            v-for="col in columns"
            :key="col.key"
            :style="{ width: col.width, textAlign: col.align ?? 'left' }"
            :class="{ 'is-sortable': col.sortable }"
            :aria-sort="sortKey === col.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : undefined"
            :tabindex="col.sortable ? 0 : undefined"
            :aria-label="col.sortable ? `Sort by ${col.label}` : undefined"
            @click="col.sortable && emit('sort', col.key)"
            @keydown.enter.prevent="col.sortable && emit('sort', col.key)"
            @keydown.space.prevent="col.sortable && emit('sort', col.key)"
          >
            <span class="vip-table__th">
              {{ col.label }}
              <VipIcon
                v-if="col.sortable && sortKey === col.key"
                :name="sortDir === 'asc' ? 'chevronUp' : 'chevronDown'"
                :size="13"
              />
            </span>
          </th>
        </tr>
      </thead>
      <tbody v-if="loading">
        <tr v-for="n in skeletonRows" :key="`sk-${n}`">
          <td v-if="selectable"><VipSkeleton width="16px" height="16px" /></td>
          <td v-for="col in columns" :key="col.key"><VipSkeleton :width="`${40 + ((n * 13) % 45)}%`" /></td>
        </tr>
      </tbody>
      <tbody v-else>
        <tr
          v-for="row in rows"
          :key="rowKey(row)"
          :class="{ 'is-clickable': clickable, 'is-selected': selected?.includes(rowKey(row)) }"
          :tabindex="clickable ? 0 : undefined"
          @click="clickable && emit('rowClick', row)"
          @keydown.enter="clickable && emit('rowClick', row)"
        >
          <td v-if="selectable" class="vip-table__check" @click.stop>
            <VipCheckbox :model-value="selected?.includes(rowKey(row))" @update:model-value="toggleRow(row)" />
          </td>
          <td v-for="col in columns" :key="col.key" :style="{ textAlign: col.align ?? 'left' }">
            <slot :name="`cell-${col.key}`" :row="row" :value="cellValue(col, row)">
              {{ cellValue(col, row) }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
    <VipEmptyState
      v-if="!loading && rows.length === 0"
      :title="emptyTitle"
      :description="emptyDescription"
      icon="table"
    />
  </div>
</template>

<style scoped>
.vip-table-wrap {
  width: 100%;
  overflow-x: auto;
}
.vip-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--vip-fs-md);
}
.vip-table thead th {
  text-align: left;
  font-size: var(--vip-fs-xs);
  font-weight: var(--vip-fw-semibold);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
  border-bottom: 1px solid var(--vip-border);
  white-space: nowrap;
  position: sticky;
  top: 0;
  background: var(--vip-surface-1);
  z-index: 1;
}
.is-comfortable thead th {
  padding: var(--vip-sp-4) var(--vip-sp-5);
}
.is-compact thead th {
  padding: var(--vip-sp-3) var(--vip-sp-5);
}
.vip-table th.is-sortable {
  cursor: pointer;
  user-select: none;
}
.vip-table th.is-sortable:hover {
  color: var(--vip-text-primary);
}
.vip-table__th {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
}
.vip-table tbody td {
  border-bottom: 1px solid var(--vip-border-subtle);
  color: var(--vip-text-secondary);
  vertical-align: middle;
}
.is-comfortable tbody td {
  padding: var(--vip-sp-5);
}
.is-compact tbody td {
  padding: var(--vip-sp-3) var(--vip-sp-5);
}
.vip-table tbody tr.is-clickable {
  cursor: pointer;
}
.vip-table tbody tr.is-clickable:hover {
  background: var(--vip-surface-hover);
}
.vip-table tbody tr.is-selected {
  background: var(--vip-brand-soft);
}
.vip-table__check {
  width: 40px;
}
</style>
