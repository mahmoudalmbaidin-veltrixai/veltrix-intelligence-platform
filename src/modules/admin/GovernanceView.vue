<script setup lang="ts">
import { computed } from 'vue'
import { useAuthorizationStore } from '@/shared/stores/authorization'
import { usePlatformStore } from '@/shared/stores/platform'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'

const platform = usePlatformStore()
const authorization = useAuthorizationStore()
const features = computed(() => Object.entries(platform.featureFlags).sort(([a], [b]) => a.localeCompare(b)))
const entitlements = computed(() => [...authorization.entitlements].sort())
const quotas = computed(() => Object.values(authorization.quotas).sort((a, b) => a.key.localeCompare(b.key)))
const label = (key: string) => key.replace(/[._-]/g, ' ').replace(/\b\w/g, (value) => value.toUpperCase())
</script>

<template>
  <div>
    <VipPageHeader
      title="Governance"
      description="Server-resolved features, entitlements, quotas, and effective access for the active tenant."
    />
    <VipAlert tone="info" title="Backend-authoritative policy">
      This view is read-only because B3 provides policy evaluation and auditability, not policy mutation APIs.
    </VipAlert>

    <section class="gov-section">
      <h2>Feature flags</h2>
      <div class="gov-grid">
        <VipCard v-for="[key, enabled] in features" :key="key" class="gov-row">
          <span>{{ label(key) }}</span>
          <VipBadge :tone="enabled ? 'success' : 'neutral'" size="sm">{{ enabled ? 'enabled' : 'disabled' }}</VipBadge>
        </VipCard>
      </div>
    </section>

    <section class="gov-section">
      <h2>Entitlements</h2>
      <div class="gov-grid">
        <VipCard v-for="key in entitlements" :key="key" class="gov-row">
          <span>{{ label(key) }}</span
          ><VipBadge tone="brand" size="sm">granted</VipBadge>
        </VipCard>
      </div>
    </section>

    <section class="gov-section">
      <h2>Quotas</h2>
      <div class="gov-grid">
        <VipCard v-for="quota in quotas" :key="quota.key" class="gov-row">
          <div>
            <strong>{{ label(quota.key) }}</strong>
            <p>{{ quota.used }} used · {{ quota.remaining }} remaining</p>
          </div>
          <VipBadge :tone="quota.remaining > 0 ? 'success' : 'warning'" size="sm">
            {{ quota.limit }} {{ quota.hard ? 'hard limit' : 'soft limit' }}
          </VipBadge>
        </VipCard>
      </div>
    </section>
  </div>
</template>

<style scoped>
.gov-section {
  margin-top: var(--vip-sp-7);
  max-width: 900px;
}
.gov-section h2 {
  margin-bottom: var(--vip-sp-4);
}
.gov-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--vip-sp-4);
}
.gov-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-5);
}
.gov-row p {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-xs);
  margin-top: var(--vip-sp-2);
}
</style>
