<script setup lang="ts">
import { ref, watch } from 'vue'
import { accessService, type ResourceSearchItem } from './access.service'
import { formatDateTime } from '@/shared/lib/format'
import { safeErrorText } from '@/shared/lib/safeError'
import VipInput from '@/shared/ui/VipInput.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

/**
 * Tenant-scoped searchable resource picker. Replaces manual UUID entry as the
 * primary workflow for choosing a resource to share/inspect. Reports and other
 * types without a searchable backend simply return no results, and the caller
 * may fall back to manual ID entry.
 */
const props = defineProps<{ resourceType: string; modelValue: string }>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'select', value: ResourceSearchItem): void
}>()

const query = ref('')
const results = ref<ResourceSearchItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const selectedLabel = ref('')
let timer: ReturnType<typeof setTimeout> | null = null

async function runSearch(q: string) {
  if (!props.resourceType) return
  loading.value = true
  error.value = null
  try {
    results.value = await accessService.searchResources(props.resourceType, q)
  } catch (e) {
    error.value = safeErrorText(e)
    results.value = []
  } finally {
    loading.value = false
  }
}

watch(query, (value) => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => void runSearch(value.trim()), 250)
})

watch(
  () => props.resourceType,
  () => {
    query.value = ''
    selectedLabel.value = ''
    results.value = []
    emit('update:modelValue', '')
  },
)

function choose(item: ResourceSearchItem) {
  selectedLabel.value = item.name
  query.value = ''
  results.value = []
  emit('update:modelValue', item.id)
  emit('select', item)
}
function clearSelection() {
  selectedLabel.value = ''
  emit('update:modelValue', '')
}
function focusSearch() {
  if (!results.value.length && !query.value) void runSearch('')
}
</script>

<template>
  <div class="rp">
    <div v-if="modelValue && selectedLabel" class="rp-selected">
      <VipIcon name="shield" :size="15" />
      <span class="rp-selected__name">{{ selectedLabel }}</span>
      <code class="rp-selected__id">{{ modelValue }}</code>
      <button type="button" class="rp-clear" aria-label="Clear selection" @click="clearSelection">
        <VipIcon name="close" :size="14" />
      </button>
    </div>
    <div v-else class="rp-search">
      <VipInput
        v-model="query"
        icon="search"
        :placeholder="`Search ${resourceType || 'resources'} by name`"
        autocomplete="off"
        @focus="focusSearch"
      />
      <ul v-if="results.length" class="rp-results" role="listbox">
        <li v-for="item in results" :key="item.id">
          <button type="button" class="rp-result" @click="choose(item)">
            <span class="rp-result__text">
              <span class="rp-result__name">{{ item.name }}</span>
              <span class="rp-result__meta">
                <code>{{ item.id }}</code>
                <span v-if="item.updated_at"> · {{ formatDateTime(item.updated_at) }}</span>
              </span>
            </span>
            <VipBadge v-if="item.status" tone="neutral" size="sm">{{ item.status }}</VipBadge>
          </button>
        </li>
      </ul>
      <p v-else-if="loading" class="rp-empty">Searching…</p>
      <p v-else-if="query.trim().length >= 1" class="rp-empty">No matching resources.</p>
    </div>
    <p v-if="error" class="rp-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.rp {
  position: relative;
}
.rp-selected {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
  padding: var(--vip-sp-2) var(--vip-sp-3);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-subtle);
}
.rp-selected__name {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.rp-selected__id {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  margin-left: auto;
}
.rp-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: none;
  color: var(--vip-text-secondary);
  border-radius: var(--vip-radius-sm);
  cursor: pointer;
}
.rp-clear:hover {
  background: var(--vip-surface-hover);
}
.rp-results {
  list-style: none;
  margin: var(--vip-sp-2) 0 0;
  padding: var(--vip-sp-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface);
  box-shadow: var(--vip-shadow-md);
  max-height: 240px;
  overflow-y: auto;
  position: absolute;
  z-index: 20;
  width: 100%;
}
.rp-result {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  width: 100%;
  padding: var(--vip-sp-2) var(--vip-sp-3);
  background: none;
  border: none;
  border-radius: var(--vip-radius-sm);
  cursor: pointer;
  text-align: left;
}
.rp-result:hover {
  background: var(--vip-surface-hover);
}
.rp-result__text {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}
.rp-result__name {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.rp-result__meta {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.rp-empty {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  padding: var(--vip-sp-2) 0;
}
.rp-error {
  font-size: var(--vip-fs-xs);
  color: var(--vip-danger-text, var(--vip-text-muted));
  margin-top: var(--vip-sp-2);
}
</style>
