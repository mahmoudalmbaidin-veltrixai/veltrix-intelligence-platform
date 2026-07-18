<script setup lang="ts">
import { ref } from 'vue'
import type { Dashboard } from '@/shared/types/dashboard'
import type { QueryFilter } from '@/shared/types/semantic'
import { MODELS } from '@/shared/services/semanticModels'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipButton from '@/shared/ui/VipButton.vue'

defineProps<{ dashboard: Dashboard; crossFilters: QueryFilter[] }>()
const emit = defineEmits<{ clearCross: []; removeCross: [QueryFilter] }>()

const dateRange = ref('last-90')
const dims = MODELS[0].fields.filter((f) => f.role === 'dimension')

const addItems = dims.map((d) => ({ key: d.id, label: d.label, icon: 'filter' }))
const localFilters = ref<QueryFilter[]>([])

const VALUES: Record<string, string[]> = {
  region: ['EMEA', 'Americas', 'APAC', 'MEA'],
  category: ['Software', 'Hardware', 'Services', 'Support', 'Training'],
  segment: ['Enterprise', 'Mid-Market', 'SMB', 'Public Sector'],
  channel: ['Direct', 'Partner', 'Self-Serve', 'Marketplace'],
}
function addFilter(fieldId: string) {
  const first = VALUES[fieldId]?.[0] ?? 'All'
  localFilters.value.push({ fieldId, operator: 'eq', value: first, label: `${fieldId} = ${first}` })
}
function removeFilter(f: QueryFilter) {
  localFilters.value = localFilters.value.filter((x) => x !== f)
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
        <VipIcon name="filter" :size="11" />{{ f.label }}
        <button @click="removeFilter(f)"><VipIcon name="close" :size="11" /></button>
      </span>
      <span v-for="f in crossFilters" :key="`x-${f.label}`" class="fbar__chip is-cross">
        <VipIcon name="link" :size="11" />{{ f.label }}
        <button @click="emit('removeCross', f)"><VipIcon name="close" :size="11" /></button>
      </span>
    </div>

    <VipMenu :items="addItems" @select="addFilter">
      <template #trigger><VipButton variant="tertiary" size="xs" icon="plus">Filter</VipButton></template>
    </VipMenu>
    <VipButton
      v-if="localFilters.length || crossFilters.length"
      variant="ghost"
      size="xs"
      icon="refresh"
      @click="((localFilters = []), emit('clearCross'))"
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
.fbar__spacer {
  flex: 1;
}
.fbar__dash-name {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-disabled);
}
</style>
