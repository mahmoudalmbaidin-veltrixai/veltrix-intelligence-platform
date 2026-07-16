<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { CONNECTORS, type Connector, type ConnectorCategory, type ConnectorAvailability } from './connections.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const router = useRouter()

type CategoryFilter = 'all' | ConnectorCategory

const categoryOptions: { value: CategoryFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'Databases', label: 'Databases' },
  { value: 'Files', label: 'Files' },
  { value: 'APIs', label: 'APIs' },
  { value: 'Cloud Storage', label: 'Cloud Storage' },
  { value: 'Business Apps', label: 'Business Apps' },
]

const category = ref<CategoryFilter>('all')
const search = ref('')

const filtered = computed<Connector[]>(() => {
  const q = search.value.trim().toLowerCase()
  return CONNECTORS.filter((c) => {
    const inCategory = category.value === 'all' || c.category === category.value
    const inSearch =
      !q ||
      c.label.toLowerCase().includes(q) ||
      c.description.toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q)
    return inCategory && inSearch
  })
})

const STATUS_TONE: Record<ConnectorAvailability, 'success' | 'info' | 'neutral' | 'warning'> = {
  available: 'success',
  beta: 'info',
  'coming-soon': 'neutral',
  restricted: 'warning',
}
const STATUS_LABEL: Record<ConnectorAvailability, string> = {
  available: 'Available',
  beta: 'Beta',
  'coming-soon': 'Coming soon',
  restricted: 'Restricted',
}

function connect(c: Connector) {
  if (c.status === 'coming-soon') return
  router.push('/connections/new')
}
</script>

<template>
  <div class="cat">
    <VipPageHeader
      title="Connector catalog"
      description="Choose a connector to bring a new source of data into the platform."
    >
      <template #actions>
        <VipButton variant="tertiary" icon="chevronLeft" @click="router.push('/connections')">
          Back to connections
        </VipButton>
      </template>
    </VipPageHeader>

    <div class="cat__controls">
      <VipSegmented v-model="category" :options="categoryOptions" size="md" />
      <div class="cat__search">
        <VipInput v-model="search" icon="search" size="sm" placeholder="Search connectors" />
      </div>
    </div>

    <div v-if="filtered.length" class="cat__grid">
      <div
        v-for="c in filtered"
        :key="c.key"
        class="cat__card"
        :class="{ 'is-disabled': c.status === 'coming-soon' }"
      >
        <div class="cat__card-top">
          <span class="cat__card-icon"><VipIcon :name="c.icon" :size="20" /></span>
          <VipBadge :tone="STATUS_TONE[c.status]" variant="soft" size="sm">
            {{ STATUS_LABEL[c.status] }}
          </VipBadge>
        </div>
        <div class="cat__card-body">
          <h3 class="cat__card-title">{{ c.label }}</h3>
          <span class="cat__card-cat">{{ c.category }}</span>
          <p class="cat__card-desc">{{ c.description }}</p>
        </div>
        <div class="cat__card-foot">
          <VipButton
            v-if="c.status === 'available'"
            variant="primary"
            size="sm"
            icon="plus"
            block
            @click="connect(c)"
          >
            Connect
          </VipButton>
          <VipButton
            v-else-if="c.status === 'beta'"
            variant="secondary"
            size="sm"
            icon="sparkles"
            block
            @click="connect(c)"
          >
            Try the beta
          </VipButton>
          <VipButton
            v-else-if="c.status === 'restricted'"
            variant="tertiary"
            size="sm"
            icon="lock"
            block
            @click="connect(c)"
          >
            Request access
          </VipButton>
          <VipButton v-else variant="ghost" size="sm" icon="clock" block disabled>
            Coming soon
          </VipButton>
        </div>
      </div>
    </div>

    <VipEmptyState
      v-else
      icon="search"
      title="No connectors match"
      description="Try a different category or search term."
    />
  </div>
</template>

<style scoped>
.cat { max-width: 1280px; margin: 0 auto; }
.cat__controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-5);
  margin-bottom: var(--vip-sp-7);
  flex-wrap: wrap;
}
.cat__search { width: min(300px, 100%); }
.cat__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--vip-sp-6);
}
.cat__card {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-lg);
  padding: var(--vip-sp-6);
  transition: border-color var(--vip-motion-fast), box-shadow var(--vip-motion-fast);
}
.cat__card:hover:not(.is-disabled) { border-color: var(--vip-border-strong); box-shadow: var(--vip-shadow-sm); }
.cat__card.is-disabled { opacity: 0.65; }
.cat__card-top { display: flex; align-items: center; justify-content: space-between; }
.cat__card-icon {
  width: 40px; height: 40px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.cat__card-body { flex: 1; }
.cat__card-title { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); }
.cat__card-cat { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.cat__card-desc { font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); margin-top: var(--vip-sp-4); line-height: var(--vip-lh-normal); }
.cat__card-foot { margin-top: auto; }
</style>
