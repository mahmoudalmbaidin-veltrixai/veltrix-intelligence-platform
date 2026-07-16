<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { relativeTime, formatDateTime } from '@/shared/lib/format'
import { operationsService, type ActivityEvent, type ActivityDomain } from './operations.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'

const { data, isLoading } = useQuery('operations:activity', (signal) =>
  operationsService.listActivity().then((r) => {
    signal.throwIfAborted()
    return r
  }),
)

const DOMAIN_META: Record<ActivityDomain, { label: string; icon: string; tone: 'brand' | 'success' | 'warning' | 'danger' | 'info' | 'neutral' }> = {
  pipeline: { label: 'Pipelines', icon: 'workflow', tone: 'brand' },
  dataset: { label: 'Datasets', icon: 'database', tone: 'info' },
  dashboard: { label: 'Dashboards', icon: 'chart', tone: 'success' },
  report: { label: 'Reports', icon: 'report', tone: 'warning' },
  ai: { label: 'AI', icon: 'sparkles', tone: 'brand' },
  automation: { label: 'Automation', icon: 'bot', tone: 'info' },
  admin: { label: 'Admin', icon: 'shield', tone: 'neutral' },
  billing: { label: 'Billing', icon: 'card', tone: 'warning' },
}

type DomainFilter = 'all' | ActivityDomain
const filter = ref<DomainFilter>('all')
const domainOptions = computed<{ value: DomainFilter; label: string; icon?: string }[]>(() => [
  { value: 'all', label: 'All' },
  ...(Object.keys(DOMAIN_META) as ActivityDomain[]).map((d) => ({
    value: d,
    label: DOMAIN_META[d].label,
    icon: DOMAIN_META[d].icon,
  })),
])

const events = computed<ActivityEvent[]>(() => data.value ?? [])
const filtered = computed(() =>
  filter.value === 'all' ? events.value : events.value.filter((e) => e.domain === filter.value),
)

interface DayGroup {
  key: string
  label: string
  events: ActivityEvent[]
}

function dayLabel(iso: string): string {
  const d = new Date(iso)
  const today = new Date()
  const yesterday = new Date(Date.now() - 86_400_000)
  if (d.toDateString() === today.toDateString()) return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })
}

const grouped = computed<DayGroup[]>(() => {
  const map = new Map<string, DayGroup>()
  for (const e of filtered.value) {
    const key = new Date(e.ts).toDateString()
    if (!map.has(key)) map.set(key, { key, label: dayLabel(e.ts), events: [] })
    map.get(key)!.events.push(e)
  }
  return [...map.values()]
})
</script>

<template>
  <div class="act">
    <VipPageHeader
      title="Activity"
      description="A chronological feed of everything happening across your organization."
    >
      <template #tabs>
        <VipSegmented v-model="filter" :options="domainOptions" size="sm" />
      </template>
    </VipPageHeader>

    <VipCard>
      <div v-if="isLoading" class="act__loading">
        <VipSkeleton v-for="i in 6" :key="i" height="40px" block />
      </div>
      <VipEmptyState
        v-else-if="!filtered.length"
        icon="activity"
        title="No activity"
        description="No events match the selected domain."
      />
      <div v-else class="act__groups">
        <section v-for="group in grouped" :key="group.key" class="act__group">
          <h2 class="act__day">{{ group.label }}</h2>
          <ol class="act__timeline">
            <li v-for="e in group.events" :key="e.id" class="act__event">
              <span class="act__marker" :class="`is-${DOMAIN_META[e.domain].tone}`">
                <VipIcon :name="DOMAIN_META[e.domain].icon" :size="14" />
              </span>
              <div class="act__content">
                <p class="act__text">
                  <strong>{{ e.actor }}</strong>
                  {{ e.action }}
                  <span class="act__target">{{ e.target }}</span>
                </p>
                <div class="act__meta">
                  <VipBadge :tone="DOMAIN_META[e.domain].tone" variant="soft" size="sm">
                    {{ DOMAIN_META[e.domain].label }}
                  </VipBadge>
                  <span class="act__time" :title="formatDateTime(e.ts)">{{ relativeTime(e.ts) }}</span>
                </div>
              </div>
            </li>
          </ol>
        </section>
      </div>
    </VipCard>
  </div>
</template>

<style scoped>
.act { max-width: 900px; margin: 0 auto; }
.act__loading { display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.act__groups { display: flex; flex-direction: column; gap: var(--vip-sp-7); }
.act__day {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-muted);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  margin-bottom: var(--vip-sp-5);
}
.act__timeline { list-style: none; margin: 0; padding: 0; position: relative; }
.act__timeline::before {
  content: '';
  position: absolute;
  left: 15px; top: 4px; bottom: 4px;
  width: 1px;
  background: var(--vip-border-subtle);
}
.act__event { display: flex; gap: var(--vip-sp-5); padding-bottom: var(--vip-sp-6); position: relative; }
.act__event:last-child { padding-bottom: 0; }
.act__marker {
  width: 32px; height: 32px; flex: none; z-index: 1;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: var(--vip-radius-full);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
}
.act__marker.is-brand { color: var(--vip-brand-text); background: var(--vip-brand-soft); border-color: transparent; }
.act__marker.is-success { color: var(--vip-success-text); background: var(--vip-success-soft); border-color: transparent; }
.act__marker.is-warning { color: var(--vip-warning-text); background: var(--vip-warning-soft); border-color: transparent; }
.act__marker.is-danger { color: var(--vip-danger-text); background: var(--vip-danger-soft); border-color: transparent; }
.act__marker.is-info { color: var(--vip-info-text); background: var(--vip-info-soft); border-color: transparent; }
.act__content { flex: 1; padding-top: var(--vip-sp-2); }
.act__text { font-size: var(--vip-fs-md); color: var(--vip-text-secondary); margin: 0; }
.act__text strong { color: var(--vip-text-primary); font-weight: var(--vip-fw-semibold); }
.act__target { color: var(--vip-text-primary); font-weight: var(--vip-fw-medium); }
.act__meta { display: flex; align-items: center; gap: var(--vip-sp-4); margin-top: var(--vip-sp-3); }
.act__time { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
</style>
