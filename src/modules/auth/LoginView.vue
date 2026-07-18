<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/shared/stores/auth'
import { config } from '@/shared/config/env'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const expired = computed(() => route.query.expired === '1')

// Prefill demo credentials ONLY in local mock mode — never in live/staging (M012).
const isDemo = config.apiMode === 'mock' && !config.isProd && config.appEnv !== 'staging'
const email = ref(isDemo ? 'mahmoud.almbaidin@shabakkatksa.com' : '')
const password = ref(isDemo ? 'demo-password' : '')
const submitting = ref(false)

const fieldError = (field: string) => auth.error?.fieldErrors?.find((f) => f.field === field)?.message

async function submit() {
  submitting.value = true
  const ok = await auth.login(email.value, password.value)
  submitting.value = false
  if (ok) router.replace(auth.takeIntended())
}
const generalError = computed(() => (auth.error && !auth.error.fieldErrors?.length ? auth.error.friendlyMessage : ''))
</script>

<template>
  <div class="login">
    <div class="login__card">
      <div class="login__brand">
        <span class="login__mark">
          <svg width="22" height="22" viewBox="0 0 32 32"><path d="M8 9l5 14 3-8 3 8 5-14" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </span>
        <span class="login__word">VIP</span>
      </div>
      <h1 class="login__title">Sign in to Veltrix Intelligence</h1>
      <p class="login__sub">Enterprise analytics, pipelines and AI in one platform.</p>

      <VipAlert v-if="expired" tone="warning" title="Session expired">Your session ended. Please sign in again to continue.</VipAlert>
      <VipAlert v-if="generalError" tone="danger" title="Sign-in failed">{{ generalError }}</VipAlert>

      <form class="login__form" @submit.prevent="submit">
        <VipInput v-model="email" label="Work email" type="email" icon="users" :error="fieldError('email')" required />
        <VipInput v-model="password" label="Password" type="password" icon="lock" :error="fieldError('password')" required />
        <VipButton type="submit" variant="primary" size="lg" block :loading="submitting">Sign in</VipButton>
      </form>

      <p v-if="config.apiMode === 'mock'" class="login__note">
        Mock mode — any non-empty credentials sign you in. Set <code>VITE_API_MODE=live</code> to use the real backend.
      </p>
    </div>
  </div>
</template>

<style scoped>
.login { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: var(--vip-sp-8); background: var(--vip-bg-app); }
.login__card { width: 100%; max-width: 400px; background: var(--vip-surface-1); border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-xl); padding: var(--vip-sp-9); box-shadow: var(--vip-shadow-lg); }
.login__brand { display: flex; align-items: center; gap: var(--vip-sp-4); margin-bottom: var(--vip-sp-7); }
.login__mark { width: 34px; height: 34px; border-radius: var(--vip-radius-md); background: linear-gradient(135deg, var(--vip-brand-500), var(--vip-brand-accent)); color: #fff; display: inline-flex; align-items: center; justify-content: center; }
.login__word { font-size: var(--vip-fs-xl); font-weight: var(--vip-fw-bold); letter-spacing: 0.06em; }
.login__title { font-size: var(--vip-fs-2xl); font-weight: var(--vip-fw-semibold); }
.login__sub { color: var(--vip-text-muted); margin: var(--vip-sp-3) 0 var(--vip-sp-7); }
.login__form { display: flex; flex-direction: column; gap: var(--vip-sp-6); }
.login__note { margin-top: var(--vip-sp-7); font-size: var(--vip-fs-xs); color: var(--vip-text-muted); text-align: center; }
.login__note code { font-family: var(--vip-font-mono); background: var(--vip-surface-3); padding: 1px 5px; border-radius: var(--vip-radius-xs); }
</style>
