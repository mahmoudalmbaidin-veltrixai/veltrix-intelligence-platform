<script setup lang="ts">
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import type { FeatureFlagKey } from '@/shared/types/identity'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'

const platform = usePlatformStore()
const ui = useUiStore()

const meta: Record<FeatureFlagKey, { label: string; description: string; scope: string }> = {
  'pipeline-python-node': {
    label: 'Python transform node',
    description: 'Enables the Python (pandas) node in Pipeline Studio.',
    scope: 'workspace',
  },
  'dashboard-map-widget': {
    label: 'Map visual',
    description: 'Geospatial map widget in Dashboard Studio.',
    scope: 'workspace',
  },
  'insights-nlq': {
    label: 'Natural-language insights',
    description: 'Ask-a-question entry point on the Insights page.',
    scope: 'organization',
  },
  'ai-agents-beta': {
    label: 'AI Agents (beta)',
    description: 'Autonomous agent builder and runs.',
    scope: 'organization',
  },
  'marketplace-extensions': {
    label: 'Marketplace extensions',
    description: 'Install third-party extensions.',
    scope: 'plan',
  },
  'report-approvals': {
    label: 'Report approvals',
    description: 'Approval workflow before report publishing.',
    scope: 'workspace',
  },
}
const keys = Object.keys(meta) as FeatureFlagKey[]
function toggle(k: FeatureFlagKey) {
  platform.toggleFlag(k)
  ui.pushToast({
    kind: 'info',
    title: 'Flag updated',
    message: `${meta[k].label}: ${platform.flagEnabled(k) ? 'on' : 'off'}`,
  })
}
function scopeTone(s: string) {
  return s === 'plan' ? 'warning' : s === 'organization' ? 'brand' : 'info'
}
</script>

<template>
  <div>
    <VipPageHeader
      title="Feature Flags"
      description="Toggle platform capabilities. Changes take effect immediately for the current context."
    />
    <div class="ff">
      <VipCard v-for="k in keys" :key="k" class="ff-row">
        <div class="ff-info">
          <div class="ff-head">
            <span class="ff-name">{{ meta[k].label }}</span
            ><VipBadge :tone="scopeTone(meta[k].scope)" size="sm">{{ meta[k].scope }}</VipBadge>
          </div>
          <p class="ff-desc">{{ meta[k].description }}</p>
        </div>
        <VipSwitch
          :model-value="platform.flagEnabled(k)"
          :aria-label="`Toggle ${meta[k].label}`"
          @update:model-value="toggle(k)"
        />
      </VipCard>
    </div>
    <p class="ff-foot">
      Percentage rollout and change history are backend-managed; overrides here apply to your active org/workspace.
    </p>
  </div>
</template>

<style scoped>
.ff {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
  max-width: 780px;
}
.ff-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-6);
}
.ff-head {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
}
.ff-name {
  font-weight: var(--vip-fw-semibold);
}
.ff-desc {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin-top: var(--vip-sp-2);
}
.ff-foot {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-disabled);
  margin-top: var(--vip-sp-6);
  max-width: 780px;
}
</style>
