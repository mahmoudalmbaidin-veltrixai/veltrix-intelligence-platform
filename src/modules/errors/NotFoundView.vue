<script setup lang="ts">
import { useRouter } from 'vue-router'
import VipButton from '@/shared/ui/VipButton.vue'
const router = useRouter()
</script>

<template>
  <div class="err">
    <div class="err__code">404</div>
    <h1 class="err__title">Page not found</h1>
    <p class="err__desc">The page you’re looking for doesn’t exist, was moved, or is unavailable in this workspace.</p>
    <div class="err__actions">
      <VipButton variant="primary" icon="home" @click="router.push('/home')">Back to Home</VipButton>
      <VipButton variant="tertiary" icon="chevronLeft" @click="router.back()">Go back</VipButton>
    </div>
  </div>
</template>

<style scoped>
.err { text-align: center; }
.err__code { font-size: 72px; font-weight: var(--vip-fw-bold); color: var(--vip-brand-text); letter-spacing: -0.03em; }
.err__title { font-size: var(--vip-fs-2xl); margin-top: var(--vip-sp-4); }
.err__desc { color: var(--vip-text-muted); margin-top: var(--vip-sp-4); }
.err__actions { display: flex; gap: var(--vip-sp-4); justify-content: center; margin-top: var(--vip-sp-7); }
</style>
