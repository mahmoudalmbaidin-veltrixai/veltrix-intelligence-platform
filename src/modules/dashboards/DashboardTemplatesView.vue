<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const router = useRouter()
const ui = useUiStore()
const platform = usePlatformStore()

interface Template {
  id: string
  name: string
  description: string
  icon: string
  category: string
  widgets: number
  model: string
}
const templates: Template[] = [
  {
    id: 'tpl_exec',
    name: 'Executive Overview',
    description: 'KPIs, revenue trend, category mix and regional breakdown for leadership.',
    icon: 'target',
    category: 'Executive',
    widgets: 8,
    model: 'Sales Analytics',
  },
  {
    id: 'tpl_revops',
    name: 'Revenue Operations',
    description: 'Channel performance, order velocity and pipeline coverage.',
    icon: 'trendUp',
    category: 'Sales',
    widgets: 6,
    model: 'Sales Analytics',
  },
  {
    id: 'tpl_finance',
    name: 'Financial Summary',
    description: 'Margin, profit and target variance with period comparisons.',
    icon: 'card',
    category: 'Finance',
    widgets: 7,
    model: 'Sales Analytics',
  },
  {
    id: 'tpl_ops',
    name: 'Platform Health',
    description: 'Traffic, error rate, latency and uptime across services.',
    icon: 'gauge',
    category: 'Operations',
    widgets: 6,
    model: 'Platform Operations',
  },
  {
    id: 'tpl_blank',
    name: 'Blank Dashboard',
    description: 'Start from an empty canvas and build your own.',
    icon: 'plus',
    category: 'General',
    widgets: 0,
    model: '—',
  },
]

function useTemplate(t: Template) {
  ui.pushToast({ kind: 'success', title: 'Template applied', message: `Creating a dashboard from “${t.name}”.` })
  router.push('/dashboards/new')
}
</script>

<template>
  <div>
    <VipPageHeader title="Dashboard Templates" description="Start faster with a curated, pre-configured layout.">
      <template #actions>
        <VipButton variant="tertiary" icon="chart" @click="router.push('/dashboards')">All dashboards</VipButton>
        <VipButton
          v-if="platform.can('dashboard.create')"
          variant="primary"
          icon="plus"
          @click="router.push('/dashboards/new')"
          >Blank dashboard</VipButton
        >
      </template>
    </VipPageHeader>
    <div class="tpl-grid">
      <VipCard v-for="t in templates" :key="t.id" class="tpl">
        <div class="tpl__icon"><VipIcon :name="t.icon" :size="20" /></div>
        <div class="tpl__name">{{ t.name }}</div>
        <VipBadge tone="neutral" size="sm">{{ t.category }}</VipBadge>
        <p class="tpl__desc">{{ t.description }}</p>
        <div class="tpl__meta">{{ t.widgets }} widgets · {{ t.model }}</div>
        <VipButton
          variant="secondary"
          size="sm"
          block
          :disabled="!platform.can('dashboard.create')"
          @click="useTemplate(t)"
          >Use template</VipButton
        >
      </VipCard>
    </div>
  </div>
</template>

<style scoped>
.tpl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--vip-sp-6);
}
.tpl {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--vip-sp-3);
}
.tpl__icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
  margin-bottom: var(--vip-sp-2);
}
.tpl__name {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.tpl__desc {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  flex: 1;
}
.tpl__meta {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-disabled);
  margin-bottom: var(--vip-sp-3);
}
.tpl :deep(.vip-btn) {
  margin-top: auto;
}
</style>
