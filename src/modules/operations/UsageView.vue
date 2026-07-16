<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { usePlatformStore } from '@/shared/stores/platform'
import { formatNumber } from '@/shared/lib/format'
import { operationsService, type UsageMetric } from './operations.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'

const platform = usePlatformStore()

const { data, isLoading } = useQuery('operations:usage', (signal) =>
  operationsService.listUsage().then((r) => {
    signal.throwIfAborted()
    return r
  }),
)

/** Merge platform entitlements (with limits) into the usage picture. */
const entitlementMetrics = computed<UsageMetric[]>(() =>
  platform.entitlements
    .filter((e) => e.limit != null && e.used != null)
    .map((e) => ({
      label: e.key.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      used: e.used ?? 0,
      limit: e.limit ?? 0,
      unit: 'entitlement',
    })),
)

const metrics = computed<UsageMetric[]>(() => [...(data.value ?? []), ...entitlementMetrics.value])

function pct(m: UsageMetric): number {
  if (!m.limit) return 0
  return Math.min(999, Math.round((m.used / m.limit) * 100))
}
function state(m: UsageMetric): 'ok' | 'warn' | 'over' {
  const p = pct(m)
  if (p >= 100) return 'over'
  if (p > 80) return 'warn'
  return 'ok'
}
function tone(m: UsageMetric): 'success' | 'warning' | 'danger' {
  const s = state(m)
  return s === 'over' ? 'danger' : s === 'warn' ? 'warning' : 'success'
}

const overCount = computed(() => metrics.value.filter((m) => state(m) === 'over').length)
const warnCount = computed(() => metrics.value.filter((m) => state(m) === 'warn').length)
</script>

<template>
  <div class="usg">
    <VipPageHeader
      title="Usage & quotas"
      description="Track consumption against the limits included in your current plan."
    >
      <template #status>
        <VipBadge tone="brand" variant="soft" size="sm">{{ platform.organization.plan }}</VipBadge>
      </template>
    </VipPageHeader>

    <VipAlert v-if="overCount" tone="danger" title="Hard limit reached">
      {{ overCount }} {{ overCount === 1 ? 'metric has' : 'metrics have' }} exceeded the plan limit.
      Additional usage may be throttled until you upgrade.
    </VipAlert>
    <VipAlert v-else-if="warnCount" tone="warning" title="Approaching limits">
      {{ warnCount }} {{ warnCount === 1 ? 'metric is' : 'metrics are' }} above 80% of the plan limit.
    </VipAlert>

    <div v-if="isLoading" class="usg__grid">
      <VipCard v-for="i in 6" :key="i">
        <VipSkeleton height="18px" width="60%" block />
        <VipSkeleton height="10px" block />
        <VipSkeleton height="34px" block />
      </VipCard>
    </div>

    <div v-else class="usg__grid">
      <VipCard v-for="m in metrics" :key="m.label" class="usg__card">
        <div class="usg__head">
          <span class="usg__label">{{ m.label }}</span>
          <VipBadge :tone="tone(m)" variant="soft" size="sm">{{ pct(m) }}%</VipBadge>
        </div>
        <div class="usg__values">
          <span class="usg__used">{{ formatNumber(m.used, { style: 'compact' }) }}</span>
          <span class="usg__limit">/ {{ formatNumber(m.limit, { style: 'compact' }) }}</span>
        </div>
        <div class="usg__bar">
          <div class="usg__fill" :class="`is-${state(m)}`" :style="{ width: `${Math.min(100, pct(m))}%` }" />
        </div>
        <span class="usg__unit">{{ m.unit }}</span>
      </VipCard>
    </div>
  </div>
</template>

<style scoped>
.usg { max-width: 1280px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--vip-sp-5); }
.usg__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--vip-sp-5);
}
.usg__card { display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.usg__head { display: flex; align-items: center; justify-content: space-between; gap: var(--vip-sp-4); }
.usg__label { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); }
.usg__values { display: flex; align-items: baseline; gap: var(--vip-sp-3); }
.usg__used { font-size: var(--vip-fs-2xl); font-weight: var(--vip-fw-semibold); color: var(--vip-text-primary); }
.usg__limit { font-size: var(--vip-fs-md); color: var(--vip-text-muted); }
.usg__bar {
  height: 8px;
  background: var(--vip-surface-3);
  border-radius: var(--vip-radius-full);
  overflow: hidden;
}
.usg__fill { height: 100%; border-radius: var(--vip-radius-full); transition: width var(--vip-motion-base) var(--vip-ease-standard); }
.usg__fill.is-ok { background: var(--vip-success); }
.usg__fill.is-warn { background: var(--vip-warning); }
.usg__fill.is-over { background: var(--vip-danger); }
.usg__unit { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
</style>
