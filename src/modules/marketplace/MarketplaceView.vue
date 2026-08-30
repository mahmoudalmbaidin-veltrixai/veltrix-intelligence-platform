<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { formatNumber } from '@/shared/lib/format'
import {
  marketplaceService,
  CATEGORY_ICON,
  type Extension,
  type ExtensionCategory,
  type ExtensionStatus,
} from './marketplace.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'

const router = useRouter()
const ui = useUiStore()

const { data, isLoading } = useQuery('marketplace:list', (signal) =>
  marketplaceService.list().then((r) => {
    signal.throwIfAborted()
    return r
  }),
)

const search = ref('')
type CategoryFilter = 'all' | ExtensionCategory
const category = ref<CategoryFilter>('all')
const categoryOptions: { value: CategoryFilter; label: string; icon?: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'Connectors', label: 'Connectors', icon: 'plug' },
  { value: 'Pipeline Nodes', label: 'Nodes', icon: 'workflow' },
  { value: 'Dashboard Widgets', label: 'Widgets', icon: 'chart' },
  { value: 'AI Tools', label: 'AI', icon: 'sparkles' },
  { value: 'Automation Actions', label: 'Automation', icon: 'bot' },
  { value: 'Templates', label: 'Templates', icon: 'layers' },
]

/** Local install state overlay so buttons react without a backend. */
const localStatus = reactive<Record<string, ExtensionStatus>>({})
function statusOf(e: Extension): ExtensionStatus {
  return localStatus[e.id] ?? e.status
}

const all = computed<Extension[]>(() => data.value ?? [])
const featured = computed(() => all.value.filter((e) => e.featured))
const filtered = computed<Extension[]>(() =>
  all.value.filter((e) => {
    if (category.value !== 'all' && e.category !== category.value) return false
    const q = search.value.trim().toLowerCase()
    if (q) {
      return (
        e.name.toLowerCase().includes(q) ||
        e.author.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q)
      )
    }
    return true
  }),
)

const STATUS_TONE: Record<ExtensionStatus, 'success' | 'brand' | 'info' | 'warning' | 'danger' | 'neutral'> = {
  installed: 'success',
  available: 'brand',
  beta: 'info',
  internal: 'neutral',
  'coming-soon': 'neutral',
  restricted: 'warning',
  incompatible: 'danger',
}
const STATUS_LABEL: Record<ExtensionStatus, string> = {
  installed: 'Installed',
  available: 'Available',
  beta: 'Beta',
  internal: 'Internal',
  'coming-soon': 'Coming soon',
  restricted: 'Restricted',
  incompatible: 'Incompatible',
}

function primaryLabel(e: Extension): string {
  const s = statusOf(e)
  if (s === 'installed') return 'Installed'
  if (s === 'coming-soon') return 'Notify me'
  if (s === 'incompatible') return 'Unavailable'
  if (s === 'internal') return 'Internal'
  if (s === 'restricted') return 'Request access'
  return 'Install'
}
function primaryDisabled(e: Extension): boolean {
  const s = statusOf(e)
  return s === 'installed' || s === 'coming-soon' || s === 'incompatible' || s === 'internal'
}

function install(e: Extension, ev: Event) {
  ev.stopPropagation()
  const s = statusOf(e)
  if (s === 'restricted') {
    ui.pushToast({ kind: 'info', title: 'Access requested', message: `${e.name} requires governance approval.` })
    return
  }
  if (primaryDisabled(e)) return
  localStatus[e.id] = 'installed'
  ui.pushToast({ kind: 'success', title: 'Extension installed', message: `${e.name} v${e.version} is now enabled.` })
}

function openExtension(e: Extension) {
  router.push(`/marketplace/${e.id}`)
}
</script>

<template>
  <div class="mkt">
    <VipPageHeader
      title="Marketplace"
      description="Extend Veltrix One with connectors, pipeline nodes, widgets, AI tools and templates."
    >
      <template #tabs>
        <VipSegmented v-model="category" :options="categoryOptions" size="sm" />
      </template>
    </VipPageHeader>

    <div class="mkt__search">
      <VipInput v-model="search" icon="search" placeholder="Search extensions by name, author or capability" />
    </div>

    <section v-if="!search && category === 'all' && featured.length" class="mkt__featured">
      <h2 class="mkt__section-title">Featured</h2>
      <div class="mkt__featured-row">
        <VipCard v-for="e in featured" :key="e.id" hoverable class="mkt__feature-card" @click="openExtension(e)">
          <div class="mkt__feature-top">
            <span class="mkt__icon is-lg"><VipIcon :name="CATEGORY_ICON[e.category]" :size="20" /></span>
            <VipBadge :tone="STATUS_TONE[statusOf(e)]" variant="soft" size="sm">
              {{ STATUS_LABEL[statusOf(e)] }}
            </VipBadge>
          </div>
          <h3 class="mkt__feature-name">{{ e.name }}</h3>
          <p class="mkt__feature-desc">{{ e.description }}</p>
          <div class="mkt__feature-meta">
            <span><VipIcon name="star" :size="13" /> {{ e.rating.toFixed(1) }}</span>
            <span>{{ formatNumber(e.installs, { style: 'compact' }) }} installs</span>
          </div>
        </VipCard>
      </div>
    </section>

    <section class="mkt__catalog">
      <div class="mkt__catalog-head">
        <h2 class="mkt__section-title">
          {{ category === 'all' ? 'All extensions' : category }}
        </h2>
        <span class="mkt__count">{{ filtered.length }} results</span>
      </div>

      <div v-if="isLoading" class="mkt__grid">
        <VipCard v-for="i in 6" :key="i">
          <VipSkeleton height="40px" width="40px" block />
          <VipSkeleton height="16px" width="70%" block />
          <VipSkeleton height="30px" block />
        </VipCard>
      </div>

      <VipEmptyState
        v-else-if="!filtered.length"
        icon="store"
        title="No extensions found"
        description="Try a different search term or category."
      />

      <div v-else class="mkt__grid">
        <VipCard v-for="e in filtered" :key="e.id" hoverable class="mkt__card" @click="openExtension(e)">
          <div class="mkt__card-top">
            <span class="mkt__icon"><VipIcon :name="CATEGORY_ICON[e.category]" :size="18" /></span>
            <VipBadge :tone="STATUS_TONE[statusOf(e)]" variant="soft" size="sm">
              {{ STATUS_LABEL[statusOf(e)] }}
            </VipBadge>
          </div>
          <h3 class="mkt__name">{{ e.name }}</h3>
          <span class="mkt__author">by {{ e.author }}</span>
          <p class="mkt__desc">{{ e.description }}</p>
          <div class="mkt__meta">
            <span class="mkt__rating"
              ><VipIcon name="star" :size="13" /> {{ e.rating ? e.rating.toFixed(1) : '—' }}</span
            >
            <span class="mkt__installs">{{ formatNumber(e.installs, { style: 'compact' }) }} installs</span>
          </div>
          <VipButton
            :variant="statusOf(e) === 'installed' ? 'secondary' : 'primary'"
            size="sm"
            block
            :disabled="primaryDisabled(e)"
            :icon="statusOf(e) === 'installed' ? 'check' : undefined"
            @click="install(e, $event)"
          >
            {{ primaryLabel(e) }}
          </VipButton>
        </VipCard>
      </div>
    </section>
  </div>
</template>

<style scoped>
.mkt {
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.mkt__search {
  width: min(480px, 100%);
}
.mkt__section-title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
}
.mkt__featured-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--vip-sp-5);
  margin-top: var(--vip-sp-4);
}
.mkt__feature-card {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.mkt__feature-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.mkt__feature-name {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
}
.mkt__feature-desc {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  line-height: var(--vip-lh-normal);
}
.mkt__feature-meta {
  display: flex;
  gap: var(--vip-sp-5);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.mkt__feature-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.mkt__catalog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--vip-sp-4);
}
.mkt__count {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.mkt__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--vip-sp-5);
}
.mkt__card {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.mkt__card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--vip-sp-2);
}
.mkt__icon {
  width: 40px;
  height: 40px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-3);
  color: var(--vip-brand-text);
}
.mkt__icon.is-lg {
  width: 44px;
  height: 44px;
}
.mkt__name {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.mkt__author {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.mkt__desc {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  line-height: var(--vip-lh-normal);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 40px;
}
.mkt__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  margin: var(--vip-sp-2) 0;
}
.mkt__rating {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--vip-warning-text);
}
</style>
