<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMutation, useQuery } from '@/shared/lib/query'
import { relativeTime } from '@/shared/lib/format'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import { semanticStudioService } from './semantic.service'
import { datasetService } from '@/modules/datasets/datasets.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipTextarea from '@/shared/ui/VipTextarea.vue'

const router = useRouter()
const ui = useUiStore()
const platform = usePlatformStore()
const canWrite = computed(() => platform.can('semantic_model.create'))

const { data, isLoading, error, refetch } = useQuery(
  () => 'semantic:models',
  () => semanticStudioService.listModels(),
)
const { data: datasets } = useQuery('semantic:datasets', () => datasetService.list())
const search = ref('')
const statusFilter = ref<'all' | 'published' | 'draft'>('all')
const page = ref(1)
const pageSize = 9
const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()
  return (data.value ?? []).filter(
    (model) =>
      (!query || model.label.toLowerCase().includes(query) || model.description.toLowerCase().includes(query)) &&
      (statusFilter.value === 'all' || (statusFilter.value === 'published' ? model.certified : !model.certified)),
  )
})
const pageCount = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize)))
const visible = computed(() => {
  const current = Math.min(page.value, pageCount.value)
  return filtered.value.slice((current - 1) * pageSize, current * pageSize)
})
watch([search, statusFilter], () => {
  page.value = 1
})

const dialogOpen = ref(false)
const formError = ref('')
const draft = reactive({
  name: '',
  key: '',
  description: '',
  datasetId: '',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  currency: 'USD',
})
const datasetOptions = computed(() => (datasets.value ?? []).map((item) => ({ value: item.id, label: item.name })))
const statusOptions = [
  { value: 'all', label: 'All statuses' },
  { value: 'published', label: 'Published' },
  { value: 'draft', label: 'Draft' },
]
function slug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function open(id: string) {
  router.push(`/semantic/${id}`)
}
function newModel() {
  if (!canWrite.value) {
    ui.pushToast({
      kind: 'warning',
      title: 'Insufficient permission',
      message: 'You need semantic:write to create a model.',
    })
    return
  }
  draft.name = ''
  draft.key = ''
  draft.description = ''
  draft.datasetId = datasetOptions.value[0]?.value ?? ''
  draft.currency = 'USD'
  formError.value = ''
  dialogOpen.value = true
}

const createModel = useMutation(
  () =>
    semanticStudioService.createModel({
      key: draft.key || slug(draft.name),
      name: draft.name.trim(),
      description: draft.description.trim(),
      primary_dataset_id: draft.datasetId,
      timezone: draft.timezone,
      currency: draft.currency.toUpperCase(),
    }),
  {
    onSuccess: async (created) => {
      dialogOpen.value = false
      await refetch()
      ui.pushToast({ kind: 'success', title: 'Semantic model created', message: draft.name })
      open(created.id)
    },
    onError: (error) => {
      formError.value = error.message
    },
  },
)

async function submit(): Promise<void> {
  draft.key = draft.key || slug(draft.name)
  if (!draft.name.trim() || draft.key.length < 2 || !draft.datasetId) {
    formError.value = 'Name, valid key, and primary dataset are required.'
    return
  }
  if (!/^[a-z][a-z0-9_]{1,99}$/.test(draft.key)) {
    formError.value = 'Key must start with a letter and contain lowercase letters, numbers, or underscores.'
    return
  }
  formError.value = ''
  await createModel.mutate(undefined)
}

function counts(dimensions: number, measures: number): string {
  return `${dimensions} dimensions · ${measures} measures`
}
</script>

<template>
  <div class="wrap">
    <VipPageHeader
      title="Semantic models"
      description="Governed, reusable definitions of your business — entities, fields, metrics and relationships."
    >
      <template #actions>
        <VipButton variant="primary" icon="plus" :disabled="!canWrite" @click="newModel">New model</VipButton>
      </template>
    </VipPageHeader>

    <div class="toolbar">
      <VipInput v-model="search" icon="search" placeholder="Search semantic models" />
      <VipSelect v-model="statusFilter" :options="statusOptions" aria-label="Model status" />
    </div>

    <div v-if="isLoading" class="grid">
      <VipCard v-for="n in 4" :key="n">
        <VipSkeleton width="42%" height="16px" />
        <VipSkeleton width="90%" height="12px" style="margin-top: 12px" />
        <VipSkeleton width="60%" height="12px" style="margin-top: 8px" />
      </VipCard>
    </div>

    <VipAlert v-else-if="error" tone="danger" title="Semantic models unavailable">
      The semantic models could not be loaded. This is a load error, not an empty workspace.
      <template #actions>
        <VipButton variant="secondary" size="sm" icon="refresh" :loading="isLoading" @click="refetch">
          Retry
        </VipButton>
      </template>
    </VipAlert>

    <VipEmptyState
      v-else-if="!data || data.length === 0"
      icon="layers"
      title="No semantic models yet"
      description="Create your first model to expose curated, query-ready business definitions."
    >
      <VipButton variant="primary" icon="plus" :disabled="!canWrite" @click="newModel">New model</VipButton>
    </VipEmptyState>

    <div v-else class="grid">
      <VipCard v-for="m in visible" :key="m.id" hoverable @click="open(m.id)">
        <div class="card-head">
          <span class="card-icon"><VipIcon name="layers" :size="18" /></span>
          <div class="card-titles">
            <div class="card-title-row">
              <h3 class="card-title">{{ m.label }}</h3>
              <VipBadge v-if="m.certified" tone="success" variant="soft" size="sm">
                <VipIcon name="shield" :size="11" /> Certified
              </VipBadge>
            </div>
            <p class="card-owner">{{ m.owner }}</p>
          </div>
        </div>
        <p class="card-desc">{{ m.description }}</p>
        <div class="card-meta">
          <span class="meta"
            ><VipIcon name="database" :size="13" /> {{ m.entities.length }}
            {{ m.entities.length === 1 ? 'entity' : 'entities' }}</span
          >
          <span class="meta"
            ><VipIcon name="hash" :size="13" />
            {{
              counts(
                m.fields.filter((f) => f.role === 'dimension' || f.role === 'time').length,
                m.fields.filter((f) => f.role === 'measure' || f.role === 'metric').length,
              )
            }}</span
          >
          <span class="meta"><VipIcon name="clock" :size="13" /> Refreshed {{ relativeTime(m.freshness) }}</span>
        </div>
      </VipCard>
    </div>
    <div v-if="pageCount > 1" class="pagination" aria-label="Semantic model pages">
      <VipButton variant="tertiary" :disabled="page === 1" @click="page--">Previous</VipButton>
      <span>Page {{ page }} of {{ pageCount }}</span>
      <VipButton variant="tertiary" :disabled="page === pageCount" @click="page++">Next</VipButton>
    </div>

    <VipDialog
      :open="dialogOpen"
      title="Create semantic model"
      description="Choose the governed dataset that anchors this semantic model."
      @close="dialogOpen = false"
    >
      <div class="form">
        <VipInput v-model="draft.name" label="Model name" required @blur="draft.key ||= slug(draft.name)" />
        <VipInput v-model="draft.key" label="Model key" required help="Stable query identifier." />
        <VipSelect v-model="draft.datasetId" :options="datasetOptions" label="Primary dataset" required />
        <VipTextarea v-model="draft.description" label="Description" />
        <div class="form-row">
          <VipInput v-model="draft.timezone" label="Timezone" required />
          <VipInput v-model="draft.currency" label="Currency" maxlength="3" required />
        </div>
        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="dialogOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="createModel.isPending.value" @click="submit"> Create model </VipButton>
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 1120px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--vip-sp-6);
}
.toolbar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 200px;
  gap: var(--vip-sp-4);
  margin-bottom: var(--vip-sp-6);
}
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--vip-sp-4);
  margin-top: var(--vip-sp-6);
  color: var(--vip-text-muted);
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 120px;
  gap: var(--vip-sp-4);
}
.form-error {
  color: var(--vip-danger-text);
  font-size: var(--vip-fs-sm);
}
.card-head {
  display: flex;
  gap: var(--vip-sp-5);
  align-items: flex-start;
}
.card-icon {
  width: 36px;
  height: 36px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
  border-radius: var(--vip-radius-md);
}
.card-titles {
  min-width: 0;
}
.card-title-row {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  flex-wrap: wrap;
}
.card-title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
}
.card-owner {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  margin-top: 2px;
}
.card-desc {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  margin-top: var(--vip-sp-5);
  line-height: var(--vip-lh-normal);
}
.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-5);
  margin-top: var(--vip-sp-6);
  padding-top: var(--vip-sp-5);
  border-top: 1px solid var(--vip-border-subtle);
}
.meta {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.card-title-row :deep(.vip-badge) {
  gap: 3px;
}
</style>
