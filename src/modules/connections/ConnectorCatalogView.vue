<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { connectionIcon, connectionService } from './connections.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const router = useRouter()
const search = ref('')
const { data: types, isLoading } = useQuery('connections:types', () => connectionService.types())
const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()
  return (types.value ?? []).filter(
    (item) => !query || `${item.name} ${item.category} ${item.description}`.toLowerCase().includes(query),
  )
})
</script>

<template>
  <div class="catalog">
    <VipPageHeader title="Connector catalog" description="Server-authoritative connector definitions and capabilities.">
      <template #actions
        ><VipButton variant="tertiary" icon="chevronLeft" @click="router.push('/connections')"
          >Back</VipButton
        ></template
      >
    </VipPageHeader>
    <VipInput v-model="search" class="catalog__search" icon="search" placeholder="Search connectors" />
    <div v-if="isLoading" class="catalog__loading">Loading connector catalog…</div>
    <div v-else-if="filtered.length" class="catalog__grid">
      <article v-for="item in filtered" :key="item.key" class="catalog__card">
        <div class="catalog__head">
          <VipIcon :name="connectionIcon(item.key)" :size="20" /><VipBadge
            :tone="item.is_enabled ? 'success' : 'neutral'"
            variant="soft"
            size="sm"
            >{{ item.is_enabled ? 'Available' : 'Disabled' }}</VipBadge
          >
        </div>
        <h3>{{ item.name }}</h3>
        <small>{{ item.category }}</small>
        <p>{{ item.description }}</p>
        <VipButton
          v-if="item.is_enabled"
          variant="primary"
          size="sm"
          block
          @click="router.push({ path: '/connections/new', query: { type: item.key } })"
          >Connect</VipButton
        >
      </article>
    </div>
    <VipEmptyState v-else icon="search" title="No connectors match" description="Try another search." />
  </div>
</template>

<style scoped>
.catalog {
  max-width: 1280px;
  margin: 0 auto;
}
.catalog__search {
  width: min(360px, 100%);
  margin-bottom: var(--vip-sp-6);
}
.catalog__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
  gap: var(--vip-sp-6);
}
.catalog__card {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-6);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-lg);
  background: var(--vip-surface-1);
}
.catalog__head {
  display: flex;
  justify-content: space-between;
}
.catalog__card small,
.catalog__card p,
.catalog__loading {
  color: var(--vip-text-muted);
}
.catalog__card p {
  flex: 1;
}
</style>
