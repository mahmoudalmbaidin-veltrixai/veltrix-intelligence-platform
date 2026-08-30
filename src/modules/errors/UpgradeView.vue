<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VipButton from '@/shared/ui/VipButton.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipLogo from '@/shared/ui/VipLogo.vue'
const route = useRoute()
const router = useRouter()

// Friendly labels for the capability keys the router guard passes through as
// `?feature=`. Falls back to a generic phrase for any unmapped key.
const FEATURE_LABELS: Record<string, string> = {
  report_studio: 'Reports',
  insights: 'Insights',
  marketplace: 'Marketplace',
  billing: 'Billing',
  ai_studio: 'AI Studio',
  developer_api: 'Developer Portal',
  automation: 'Automation Studio',
}
const featureLabel = computed(() => {
  const key = route.query.feature
  if (typeof key === 'string' && FEATURE_LABELS[key]) return FEATURE_LABELS[key]
  return 'This module'
})
</script>

<template>
  <div class="err">
    <RouterLink to="/home" class="err__brand" aria-label="Veltrix One home"
      ><VipLogo variant="full" size="md" decorative
    /></RouterLink>
    <div class="err__icon"><VipIcon name="sparkles" :size="28" /></div>
    <h1 class="err__title">Not available on this workspace</h1>
    <p class="err__desc">
      <strong>{{ featureLabel }}</strong> isn’t enabled for your organization. This module is disabled here — it isn’t a
      permission error. An administrator can enable it once it’s available for your plan.
    </p>
    <div class="err__actions">
      <VipButton variant="primary" icon="arrow-left" @click="router.push('/home')">Back to home</VipButton>
    </div>
  </div>
</template>

<style scoped>
.err {
  text-align: center;
}
.err__brand {
  display: inline-flex;
  margin-bottom: var(--vip-sp-8);
  color: var(--vip-text-primary);
  text-decoration: none;
  border-radius: var(--vip-radius-sm);
}
.err__icon {
  width: 64px;
  height: 64px;
  margin: 0 auto var(--vip-sp-6);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
  border-radius: var(--vip-radius-xl);
}
.err__title {
  font-size: var(--vip-fs-2xl);
}
.err__desc {
  color: var(--vip-text-muted);
  margin-top: var(--vip-sp-4);
}
.err__actions {
  display: flex;
  gap: var(--vip-sp-4);
  justify-content: center;
  margin-top: var(--vip-sp-7);
}
</style>
