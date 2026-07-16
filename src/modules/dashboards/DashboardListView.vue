<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { dashboardService } from './dashboards.service'
import { usePlatformStore } from '@/shared/stores/platform'
import { relativeTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'

const router = useRouter()
const platform = usePlatformStore()
const { data, isLoading } = useQuery('dashboards:list', () => dashboardService.list())

const route = useRoute()
const search = ref('')
const filter = ref<'all' | 'favorites' | 'published'>(route.name === 'dashboards-published' ? 'published' : 'all')

const items = computed(() => {
  let list = data.value ?? []
  if (filter.value === 'favorites') list = list.filter((d) => d.favorite)
  if (filter.value === 'published') list = list.filter((d) => d.status === 'published')
  const q = search.value.trim().toLowerCase()
  if (q) list = list.filter((d) => d.name.toLowerCase().includes(q) || d.tags.some((t) => t.includes(q)))
  return list
})
</script>

<template>
  <div>
    <VipPageHeader title="Dashboards" description="Explore and author interactive analytics dashboards.">
      <template #actions>
        <VipButton variant="tertiary" icon="layers" @click="router.push('/dashboards/templates')">Templates</VipButton>
        <VipButton variant="tertiary" icon="calendar" @click="router.push('/dashboards/deliveries')">Deliveries</VipButton>
        <VipButton v-if="platform.can('dashboard:write')" variant="primary" icon="plus" @click="router.push('/dashboards/new')">New dashboard</VipButton>
      </template>
    </VipPageHeader>

    <div class="dl-toolbar">
      <VipInput v-model="search" icon="search" placeholder="Search dashboards…" size="sm" />
      <VipSegmented v-model="filter" :options="[{ value: 'all', label: 'All' }, { value: 'favorites', label: 'Favorites' }, { value: 'published', label: 'Published' }]" size="sm" />
    </div>

    <div v-if="isLoading" class="dl-grid">
      <VipCard v-for="n in 6" :key="n"><VipSkeleton height="120px" block /><VipSkeleton width="60%" style="margin-top:12px" /></VipCard>
    </div>
    <div v-else class="dl-grid">
      <VipCard v-for="d in items" :key="d.id" hoverable :padded="false" class="dl-card" @click="router.push(`/dashboards/${d.id}`)">
        <div class="dl-thumb">
          <VipIcon name="chart" :size="30" />
          <VipIcon v-if="d.favorite" name="star" :size="15" class="dl-fav" />
        </div>
        <div class="dl-info">
          <div class="dl-name">{{ d.name }}</div>
          <div class="dl-meta">
            <VipBadge :tone="d.status === 'published' ? 'success' : 'neutral'" size="sm">{{ d.status }}</VipBadge>
            <span class="dl-muted">{{ d.pageCount }} pages · {{ d.widgetCount }} visuals</span>
          </div>
          <div class="dl-foot">{{ d.owner }} · {{ relativeTime(d.updatedAt) }}</div>
        </div>
      </VipCard>
    </div>
  </div>
</template>

<style scoped>
.dl-toolbar { display: flex; align-items: center; justify-content: space-between; gap: var(--vip-sp-4); margin-bottom: var(--vip-sp-6); flex-wrap: wrap; }
.dl-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--vip-sp-6); }
.dl-card { overflow: hidden; }
.dl-thumb { position: relative; height: 130px; background: linear-gradient(135deg, var(--vip-surface-2), var(--vip-surface-3)); display: flex; align-items: center; justify-content: center; color: var(--vip-text-disabled); border-bottom: 1px solid var(--vip-border-subtle); }
.dl-fav { position: absolute; top: var(--vip-sp-4); right: var(--vip-sp-4); color: var(--vip-warning); }
.dl-info { padding: var(--vip-sp-5); }
.dl-name { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); }
.dl-meta { display: flex; align-items: center; gap: var(--vip-sp-3); margin-top: var(--vip-sp-3); }
.dl-muted { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.dl-foot { font-size: var(--vip-fs-xs); color: var(--vip-text-disabled); margin-top: var(--vip-sp-3); }
</style>
