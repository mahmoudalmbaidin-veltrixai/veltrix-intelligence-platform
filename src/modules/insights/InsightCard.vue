<script setup lang="ts">
import { computed } from 'vue'
import type { Insight } from '@/shared/types/insight'
import { MODELS } from '@/shared/services/semanticModels'
import { formatNumber, formatPct, relativeTime } from '@/shared/lib/format'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import Sparkline from '@/shared/viz/Sparkline.vue'

const props = defineProps<{ insight: Insight }>()
const emit = defineEmits<{ explain: [Insight]; pin: [Insight]; save: [Insight]; share: [Insight] }>()

const kindLabel: Record<string, string> = {
  trend: 'Trend', variance: 'Variance', anomaly: 'Anomaly', 'top-increase': 'Top increase',
  'top-decrease': 'Top decrease', 'target-variance': 'Target variance', 'period-comparison': 'Period comparison',
  contribution: 'Contribution', 'key-driver': 'Key driver',
}
const kindIcon: Record<string, string> = {
  trend: 'trendUp', variance: 'activity', anomaly: 'warning', 'top-increase': 'trendUp',
  'top-decrease': 'trendDown', 'target-variance': 'target', 'period-comparison': 'chart',
  contribution: 'pieChart', 'key-driver': 'sparkles',
}
const tone = computed(() => (props.insight.sentiment === 'positive' ? 'success' : props.insight.sentiment === 'negative' ? 'danger' : 'info'))
const model = computed(() => MODELS.find((m) => m.id === props.insight.modelId)?.label ?? props.insight.modelId)
const sparkColor = computed(() => (props.insight.sentiment === 'positive' ? 'var(--vip-success)' : props.insight.sentiment === 'negative' ? 'var(--vip-danger)' : 'var(--vip-info)'))
</script>

<template>
  <VipCard class="ic" :padded="false">
    <div class="ic__head">
      <span class="ic__kind" :class="`is-${tone}`"><VipIcon :name="kindIcon[insight.kind]" :size="14" />{{ kindLabel[insight.kind] }}</span>
      <span v-if="insight.simulated" class="ic__sim" title="Generated in development mode">simulated</span>
    </div>

    <div class="ic__body">
      <h3 class="ic__title">{{ insight.title }}</h3>
      <div class="ic__metric-row">
        <div>
          <div class="ic__metric">{{ formatNumber(insight.metricValue, { style: insight.metricFormat, currency: 'USD' }) }}</div>
          <div class="ic__compare">
            <VipBadge :tone="insight.changePct >= 0 ? 'success' : 'danger'" size="sm">{{ formatPct(insight.changePct) }}</VipBadge>
            {{ insight.comparisonLabel }}
          </div>
        </div>
        <div v-if="insight.series" class="ic__spark"><Sparkline :values="insight.series.map((s) => s.value)" :color="sparkColor" area /></div>
      </div>
      <p class="ic__finding">{{ insight.finding }}</p>

      <div v-if="insight.recommendedAction" class="ic__action">
        <VipIcon name="sparkles" :size="13" />
        <span>{{ insight.recommendedAction }}</span>
      </div>

      <div class="ic__meta">
        <span title="Confidence"><VipIcon name="gauge" :size="12" /> {{ Math.round(insight.confidence * 100) }}% confidence</span>
        <span><VipIcon name="layers" :size="12" /> {{ model }}</span>
        <span><VipIcon name="clock" :size="12" /> {{ relativeTime(insight.freshness) }}</span>
      </div>
    </div>

    <footer class="ic__foot">
      <VipButton variant="ghost" size="xs" icon="sparkles" @click="emit('explain', insight)">Explain</VipButton>
      <VipButton variant="ghost" size="xs" :icon="'pin'" :active="insight.pinned" @click="emit('pin', insight)">{{ insight.pinned ? 'Pinned' : 'Pin' }}</VipButton>
      <VipButton variant="ghost" size="xs" :icon="'star'" :active="insight.saved" @click="emit('save', insight)">{{ insight.saved ? 'Saved' : 'Save' }}</VipButton>
      <VipButton variant="ghost" size="xs" icon="share" @click="emit('share', insight)">Share</VipButton>
    </footer>
  </VipCard>
</template>

<style scoped>
.ic { display: flex; flex-direction: column; height: 100%; }
.ic__head { display: flex; align-items: center; justify-content: space-between; padding: var(--vip-sp-5) var(--vip-sp-6) 0; }
.ic__kind { display: inline-flex; align-items: center; gap: var(--vip-sp-2); font-size: var(--vip-fs-xs); font-weight: var(--vip-fw-semibold); }
.ic__kind.is-success { color: var(--vip-success-text); }
.ic__kind.is-danger { color: var(--vip-danger-text); }
.ic__kind.is-info { color: var(--vip-info-text); }
.ic__sim { font-size: var(--vip-fs-2xs); color: var(--vip-text-disabled); background: var(--vip-surface-3); padding: 1px 6px; border-radius: var(--vip-radius-full); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); }
.ic__body { flex: 1; padding: var(--vip-sp-4) var(--vip-sp-6); }
.ic__title { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); }
.ic__metric-row { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--vip-sp-4); margin: var(--vip-sp-5) 0; }
.ic__metric { font-size: var(--vip-fs-2xl); font-weight: var(--vip-fw-bold); font-variant-numeric: tabular-nums; }
.ic__compare { display: flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-xs); color: var(--vip-text-muted); margin-top: var(--vip-sp-3); }
.ic__spark { width: 120px; height: 44px; }
.ic__finding { font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); line-height: var(--vip-lh-normal); }
.ic__action { display: flex; align-items: flex-start; gap: var(--vip-sp-3); margin-top: var(--vip-sp-5); padding: var(--vip-sp-4); background: var(--vip-brand-soft); color: var(--vip-brand-text); border-radius: var(--vip-radius-md); font-size: var(--vip-fs-xs); }
.ic__meta { display: flex; flex-wrap: wrap; gap: var(--vip-sp-5); margin-top: var(--vip-sp-5); font-size: var(--vip-fs-2xs); color: var(--vip-text-muted); }
.ic__meta span { display: inline-flex; align-items: center; gap: var(--vip-sp-2); }
.ic__foot { display: flex; gap: var(--vip-sp-2); padding: var(--vip-sp-3) var(--vip-sp-5); border-top: 1px solid var(--vip-border-subtle); }
</style>
