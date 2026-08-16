<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Dashboard } from '@/shared/types/dashboard'
import type { FilterOperator, QueryFilter, SemanticModel } from '@/shared/types/semantic'
import {
  buildDashboardFilter,
  defaultOperatorForField,
  draftFromFilter,
  migrateDraft,
  operatorsForField,
  valueInputType,
  type FilterDraft,
} from './filterAuthoring'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipButton from '@/shared/ui/VipButton.vue'

const props = withDefaults(
  defineProps<{
    dashboard: Dashboard
    crossFilters: QueryFilter[]
    models?: SemanticModel[]
    modelId?: string
    filters?: QueryFilter[]
  }>(),
  { models: () => [], modelId: '', filters: () => [] },
)
const emit = defineEmits<{
  clearCross: []
  removeCross: [QueryFilter]
  'update:filters': [QueryFilter[]]
}>()

const dateRange = ref('last-90')
const model = computed(() => props.models.find((item) => item.id === props.modelId) ?? props.models[0])
const dims = computed(() => (model.value?.fields ?? []).filter((f) => f.role === 'dimension' || f.role === 'time'))

const addItems = computed(() => dims.value.map((d) => ({ key: d.id, label: d.label, icon: 'filter' })))
const localFilters = ref<QueryFilter[]>([...props.filters])

// Pending authoring state — one filter row being created or edited.
const pendingFieldId = ref('')
const pendingOperator = ref<FilterOperator>('eq')
const pendingValue = ref('') // eq
const pendingValues = ref<string[]>([]) // in
const pendingToken = ref('') // in — token being typed
const pendingFrom = ref('') // between
const pendingTo = ref('') // between
const pendingError = ref('')

const pendingField = computed(() => dims.value.find((d) => d.id === pendingFieldId.value))
const operatorOptions = computed(() => (pendingField.value ? operatorsForField(pendingField.value) : []))
const valueType = computed(() => (pendingField.value ? valueInputType(pendingField.value) : 'text'))

watch(
  () => props.filters,
  (filters) => {
    localFilters.value = [...filters]
  },
  { deep: true },
)

function currentDraft(): FilterDraft {
  return { value: pendingValue.value, values: [...pendingValues.value], from: pendingFrom.value, to: pendingTo.value }
}
function applyDraft(draft: FilterDraft) {
  pendingValue.value = draft.value ?? ''
  pendingValues.value = draft.values ? [...draft.values] : []
  pendingFrom.value = draft.from ?? ''
  pendingTo.value = draft.to ?? ''
  pendingToken.value = ''
}

function addFilter(fieldId: string) {
  const field = dims.value.find((item) => item.id === fieldId)
  pendingFieldId.value = fieldId
  pendingOperator.value = field ? defaultOperatorForField(field) : 'eq'
  applyDraft({})
  pendingError.value = ''
}
function editFilter(f: QueryFilter) {
  const field = dims.value.find((item) => item.id === f.fieldId)
  if (!field) return
  pendingFieldId.value = field.id
  const { operator, draft } = draftFromFilter(f)
  // Guard against an operator the current field no longer supports.
  pendingOperator.value = operatorOptions.value.some((o) => o.value === operator)
    ? operator
    : defaultOperatorForField(field)
  applyDraft(draft)
  pendingError.value = ''
}
// Carry compatible values across an operator change so users do not retype.
function onOperatorChange() {
  applyDraft(migrateDraft(pendingOperator.value, currentDraft()))
  pendingError.value = ''
}
function addToken() {
  const value = pendingToken.value.trim()
  if (!value) return
  if (!pendingValues.value.includes(value)) pendingValues.value = [...pendingValues.value, value]
  pendingToken.value = ''
  pendingError.value = ''
}
function removeToken(index: number) {
  pendingValues.value = pendingValues.value.filter((_, i) => i !== index)
}
function commitFilter() {
  const field = pendingField.value
  if (!field) return
  // An unsubmitted `in` token is included so a single typed value still applies.
  const draft = currentDraft()
  if (pendingOperator.value === 'in' && pendingToken.value.trim()) {
    draft.values = [...(draft.values ?? []), pendingToken.value.trim()]
  }
  const result = buildDashboardFilter(field, pendingOperator.value, draft)
  if (!result.filter) {
    pendingError.value = result.error ?? 'Enter a valid filter value.'
    return
  }
  localFilters.value = [...localFilters.value.filter((item) => item.fieldId !== field.id), result.filter]
  emit('update:filters', localFilters.value)
  cancelPending()
}
function cancelPending() {
  pendingFieldId.value = ''
  pendingOperator.value = 'eq'
  applyDraft({})
  pendingError.value = ''
}
function removeFilter(f: QueryFilter) {
  localFilters.value = localFilters.value.filter((x) => x !== f)
  emit('update:filters', localFilters.value)
}
function resetFilters() {
  localFilters.value = []
  cancelPending()
  emit('update:filters', [])
  emit('clearCross')
}

const dateOptions = [
  { key: 'today', label: 'Today' },
  { key: 'last-7', label: 'Last 7 days' },
  { key: 'last-30', label: 'Last 30 days' },
  { key: 'last-90', label: 'Last 90 days' },
  { key: 'ytd', label: 'Year to date' },
  { key: 'last-12m', label: 'Last 12 months' },
]
</script>

<template>
  <div class="fbar">
    <VipMenu :items="dateOptions" align="start" @select="dateRange = $event">
      <template #trigger>
        <button class="fbar__date">
          <VipIcon name="calendar" :size="14" />{{ dateOptions.find((o) => o.key === dateRange)?.label
          }}<VipIcon name="chevronDown" :size="13" />
        </button>
      </template>
    </VipMenu>

    <div class="fbar__chips">
      <span v-for="f in localFilters" :key="f.label" class="fbar__chip">
        <button type="button" class="fbar__chip-edit" :aria-label="`Edit filter ${f.label}`" @click="editFilter(f)">
          <VipIcon name="filter" :size="11" />{{ f.label }}
        </button>
        <button :aria-label="`Remove filter ${f.label}`" @click="removeFilter(f)">
          <VipIcon name="close" :size="11" />
        </button>
      </span>
      <span v-for="f in crossFilters" :key="`x-${f.label}`" class="fbar__chip is-cross">
        <VipIcon name="link" :size="11" />{{ f.label }}
        <button @click="emit('removeCross', f)"><VipIcon name="close" :size="11" /></button>
      </span>
    </div>

    <VipMenu :items="addItems" @select="addFilter">
      <template #trigger><VipButton variant="tertiary" size="xs" icon="plus">Filter</VipButton></template>
    </VipMenu>
    <form v-if="pendingFieldId" class="fbar__value" @submit.prevent="commitFilter">
      <span class="fbar__value-label">{{ pendingField?.label }}</span>
      <select
        v-model="pendingOperator"
        class="fbar__op"
        :aria-label="`${pendingField?.label} operator`"
        @change="onOperatorChange"
      >
        <option v-for="o in operatorOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>

      <!-- eq: a single value -->
      <input
        v-if="pendingOperator === 'eq'"
        :id="`dashboard-filter-${pendingFieldId}`"
        v-model="pendingValue"
        :type="valueType"
        class="fbar__input"
        autocomplete="off"
        :aria-label="`${pendingField?.label} value`"
        placeholder="Value"
      />

      <!-- in: a set of values -->
      <template v-else-if="pendingOperator === 'in'">
        <span v-for="(v, i) in pendingValues" :key="`${v}-${i}`" class="fbar__token">
          {{ v }}
          <button type="button" :aria-label="`Remove ${v}`" @click="removeToken(i)">
            <VipIcon name="close" :size="10" />
          </button>
        </span>
        <input
          v-model="pendingToken"
          :type="valueType"
          class="fbar__input"
          autocomplete="off"
          :aria-label="`Add a ${pendingField?.label} value`"
          placeholder="Add value"
          @keydown.enter.prevent="addToken"
        />
        <VipButton type="button" variant="tertiary" size="xs" :disabled="!pendingToken.trim()" @click="addToken"
          >Add</VipButton
        >
      </template>

      <!-- between: two bounds -->
      <template v-else-if="pendingOperator === 'between'">
        <input
          v-model="pendingFrom"
          :type="valueType"
          class="fbar__input"
          autocomplete="off"
          :aria-label="`${pendingField?.label} from`"
          placeholder="From"
        />
        <span class="fbar__range-sep" aria-hidden="true">–</span>
        <input
          v-model="pendingTo"
          :type="valueType"
          class="fbar__input"
          autocomplete="off"
          :aria-label="`${pendingField?.label} to`"
          placeholder="To"
        />
      </template>

      <VipButton type="submit" variant="primary" size="xs">Apply</VipButton>
      <VipButton type="button" variant="ghost" size="xs" @click="cancelPending">Cancel</VipButton>
      <span v-if="pendingError" class="fbar__error" role="alert">{{ pendingError }}</span>
    </form>
    <VipButton
      v-if="localFilters.length || crossFilters.length"
      variant="ghost"
      size="xs"
      icon="refresh"
      @click="resetFilters"
      >Reset</VipButton
    >
    <span v-if="crossFilters.length" class="fbar__count"
      >{{ crossFilters.length }} cross-filter{{ crossFilters.length > 1 ? 's' : '' }} active</span
    >
    <span class="fbar__spacer" />
    <span class="fbar__dash-name">{{ dashboard.name }}</span>
  </div>
</template>

<style scoped>
.fbar {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4) var(--vip-sp-6);
  background: var(--vip-surface-1);
  border-bottom: 1px solid var(--vip-border-subtle);
  flex: none;
  flex-wrap: wrap;
}
.fbar__date {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
  height: 28px;
  padding: 0 var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-sm);
}
.fbar__date:hover {
  border-color: var(--vip-border-strong);
}
.fbar__chips {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  flex-wrap: wrap;
}
.fbar__chip {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  padding: 2px 4px 2px 8px;
  background: var(--vip-surface-3);
  border-radius: var(--vip-radius-full);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-secondary);
}
.fbar__chip.is-cross {
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.fbar__chip button {
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: inherit;
  border-radius: 50%;
}
.fbar__chip button:hover {
  background: rgba(125, 132, 148, 0.25);
}
.fbar__count {
  font-size: var(--vip-fs-xs);
  color: var(--vip-brand-text);
}
.fbar__value {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  flex-wrap: wrap;
}
.fbar__value-label {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-secondary);
}
.fbar__op,
.fbar__input {
  height: 28px;
  padding: 0 var(--vip-sp-3);
  color: var(--vip-text-primary);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  font-size: var(--vip-fs-sm);
}
.fbar__input {
  min-width: 120px;
}
.fbar__op:focus-visible,
.fbar__input:focus-visible {
  outline: none;
  border-color: var(--vip-brand-500);
  box-shadow: 0 0 0 3px var(--vip-brand-soft);
}
.fbar__token {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  padding: 2px 4px 2px 8px;
  background: var(--vip-surface-3);
  border-radius: var(--vip-radius-full);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-secondary);
}
.fbar__token button {
  width: 15px;
  height: 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: inherit;
  border-radius: 50%;
}
.fbar__range-sep {
  color: var(--vip-text-muted);
}
.fbar__error {
  font-size: var(--vip-fs-xs);
  color: var(--vip-danger-text);
}
.fbar__chip-edit {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  background: none;
  border: none;
  color: inherit;
  font-size: inherit;
  cursor: pointer;
  padding: 0;
}
.fbar__chip-edit:hover {
  color: var(--vip-text-primary);
}
.fbar__spacer {
  flex: 1;
}
.fbar__dash-name {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-disabled);
}
</style>
