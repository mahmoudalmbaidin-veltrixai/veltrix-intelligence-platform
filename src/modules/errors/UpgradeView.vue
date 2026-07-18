<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import VipButton from '@/shared/ui/VipButton.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
const route = useRoute()
const router = useRouter()
</script>

<template>
  <div class="err">
    <div class="err__icon"><VipIcon name="sparkles" :size="28" /></div>
    <h1 class="err__title">Upgrade required</h1>
    <p class="err__desc">
      <strong>{{ route.query.feature ?? 'This feature' }}</strong> isn’t included in your current plan. Upgrade your
      organization plan to unlock it.
    </p>
    <div class="err__actions">
      <VipButton variant="primary" icon="card" @click="router.push('/billing')">View plans</VipButton>
      <VipButton variant="tertiary" @click="router.push('/home')">Not now</VipButton>
    </div>
  </div>
</template>

<style scoped>
.err {
  text-align: center;
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
