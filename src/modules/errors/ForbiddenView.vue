<script setup lang="ts">
import { useRouter } from 'vue-router'
import { usePlatformStore } from '@/shared/stores/platform'
import { ROLES } from '@/shared/permissions/roles'
import VipButton from '@/shared/ui/VipButton.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
const router = useRouter()
const platform = usePlatformStore()
</script>

<template>
  <div class="err">
    <div class="err__icon"><VipIcon name="lock" :size="28" /></div>
    <h1 class="err__title">Access denied</h1>
    <p class="err__desc">
      Your current role (<strong>{{ ROLES[platform.role].label }}</strong>) doesn’t have permission to view this page.
      Switch roles from the top bar to explore permission-aware behavior, or contact an administrator.
    </p>
    <p class="err__note">Frontend permission checks are a UX convenience only — the backend remains the security boundary.</p>
    <div class="err__actions">
      <VipButton variant="primary" icon="home" @click="router.push('/home')">Back to Home</VipButton>
    </div>
  </div>
</template>

<style scoped>
.err { text-align: center; }
.err__icon { width: 64px; height: 64px; margin: 0 auto var(--vip-sp-6); display: flex; align-items: center; justify-content: center; background: var(--vip-danger-soft); color: var(--vip-danger-text); border-radius: var(--vip-radius-xl); }
.err__title { font-size: var(--vip-fs-2xl); }
.err__desc { color: var(--vip-text-muted); margin-top: var(--vip-sp-4); }
.err__note { color: var(--vip-text-disabled); font-size: var(--vip-fs-sm); margin-top: var(--vip-sp-5); }
.err__actions { margin-top: var(--vip-sp-7); }
</style>
