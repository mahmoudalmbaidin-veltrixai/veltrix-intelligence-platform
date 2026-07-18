<script setup lang="ts">
import { useRouter } from 'vue-router'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'

const router = useRouter()
const favorites = [
  { id: 'f1', name: 'Executive Overview', type: 'Dashboard', icon: 'chart', to: '/dashboards/db_exec' },
  { id: 'f2', name: 'Revenue Nightly ETL', type: 'Pipeline', icon: 'workflow', to: '/pipelines/pl_revenue' },
  { id: 'f3', name: 'Sales Analytics', type: 'Semantic Model', icon: 'layers', to: '/semantic/sm_sales' },
  { id: 'f4', name: 'fct_orders', type: 'Dataset', icon: 'database', to: '/datasets/ds_orders' },
]
</script>

<template>
  <div>
    <VipPageHeader title="Favorites" description="Resources you've starred for quick access across the platform." />
    <div class="fav-grid">
      <VipCard v-for="f in favorites" :key="f.id" hoverable @click="router.push(f.to)">
        <div class="fav">
          <span class="fav__icon"><VipIcon :name="f.icon" :size="18" /></span>
          <VipIcon name="star" :size="15" class="fav__star" />
        </div>
        <div class="fav__name">{{ f.name }}</div>
        <VipBadge tone="neutral" size="sm">{{ f.type }}</VipBadge>
      </VipCard>
    </div>
  </div>
</template>

<style scoped>
.fav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--vip-sp-6);
}
.fav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--vip-sp-5);
}
.fav__icon {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.fav__star {
  color: var(--vip-warning);
}
.fav__name {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  margin-bottom: var(--vip-sp-4);
}
</style>
