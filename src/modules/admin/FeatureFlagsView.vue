<script setup lang="ts">
import { usePlatformStore } from '@/shared/stores/platform'
import { computed } from 'vue'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'

const platform = usePlatformStore()
const keys = computed(() => Object.keys(platform.featureFlags).sort())
const label = (key: string) => key.replace(/_/g, ' ').replace(/\b\w/g, (value: string) => value.toUpperCase())
function scopeTone(s: string) {
  return s === 'plan' ? 'warning' : s === 'organization' ? 'brand' : 'info'
}
</script>

<template>
  <div>
    <VipPageHeader
      title="Feature Flags"
      description="Effective capabilities resolved by the backend for the active tenant context."
    />
    <div class="ff">
      <VipCard v-for="k in keys" :key="k" class="ff-row">
        <div class="ff-info">
          <div class="ff-head">
            <span class="ff-name">{{ label(k) }}</span
            ><VipBadge :tone="scopeTone('organization')" size="sm">effective</VipBadge>
          </div>
          <p class="ff-desc">Resolved from the global default and tenant override.</p>
        </div>
        <VipSwitch :model-value="platform.flagEnabled(k)" :aria-label="`${label(k)} effective status`" disabled />
      </VipCard>
    </div>
    <p class="ff-foot">Definitions and overrides are backend-managed and cannot be changed from this read-only view.</p>
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
