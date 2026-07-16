<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { relativeTime } from '@/shared/lib/format'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import { semanticStudioService } from './semantic.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const router = useRouter()
const ui = useUiStore()
const platform = usePlatformStore()
const canWrite = computed(() => platform.can('semantic:write'))

const { data, isLoading } = useQuery(
  () => 'semantic:models',
  () => semanticStudioService.listModels(),
)

function open(id: string) {
  router.push(`/semantic/${id}`)
}
function newModel() {
  if (!canWrite.value) {
    ui.pushToast({ kind: 'warning', title: 'Insufficient permission', message: 'You need semantic:write to create a model.' })
    return
  }
  ui.pushToast({ kind: 'info', title: 'New model', message: 'Model scaffolding is not available in this preview.' })
}

function counts(dimensions: number, measures: number): string {
  return `${dimensions} dimensions · ${measures} measures`
}
</script>

<template>
  <div class="wrap">
    <VipPageHeader title="Semantic models" description="Governed, reusable definitions of your business — entities, fields, metrics and relationships.">
      <template #actions>
        <VipButton variant="primary" icon="plus" :disabled="!canWrite" @click="newModel">New model</VipButton>
      </template>
    </VipPageHeader>

    <div v-if="isLoading" class="grid">
      <VipCard v-for="n in 4" :key="n">
        <VipSkeleton width="42%" height="16px" />
        <VipSkeleton width="90%" height="12px" style="margin-top: 12px" />
        <VipSkeleton width="60%" height="12px" style="margin-top: 8px" />
      </VipCard>
    </div>

    <VipEmptyState
      v-else-if="!data || data.length === 0"
      icon="layers"
      title="No semantic models yet"
      description="Create your first model to expose curated, query-ready business definitions."
    >
      <VipButton variant="primary" icon="plus" :disabled="!canWrite" @click="newModel">New model</VipButton>
    </VipEmptyState>

    <div v-else class="grid">
      <VipCard
        v-for="m in data"
        :key="m.id"
        hoverable
        @click="open(m.id)"
      >
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
          <span class="meta"><VipIcon name="database" :size="13" /> {{ m.entities.length }} {{ m.entities.length === 1 ? 'entity' : 'entities' }}</span>
          <span class="meta"><VipIcon name="hash" :size="13" /> {{ counts(m.fields.filter((f) => f.role === 'dimension' || f.role === 'time').length, m.fields.filter((f) => f.role === 'measure' || f.role === 'metric').length) }}</span>
          <span class="meta"><VipIcon name="clock" :size="13" /> Refreshed {{ relativeTime(m.freshness) }}</span>
        </div>
      </VipCard>
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 1120px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--vip-sp-6); }
.card-head { display: flex; gap: var(--vip-sp-5); align-items: flex-start; }
.card-icon {
  width: 36px; height: 36px; flex: none;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--vip-brand-soft); color: var(--vip-brand-text);
  border-radius: var(--vip-radius-md);
}
.card-titles { min-width: 0; }
.card-title-row { display: flex; align-items: center; gap: var(--vip-sp-4); flex-wrap: wrap; }
.card-title { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); color: var(--vip-text-primary); }
.card-owner { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); margin-top: 2px; }
.card-desc { font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); margin-top: var(--vip-sp-5); line-height: var(--vip-lh-normal); }
.card-meta { display: flex; flex-wrap: wrap; gap: var(--vip-sp-5); margin-top: var(--vip-sp-6); padding-top: var(--vip-sp-5); border-top: 1px solid var(--vip-border-subtle); }
.meta { display: inline-flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.card-title-row :deep(.vip-badge) { gap: 3px; }
</style>
