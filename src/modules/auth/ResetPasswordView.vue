<script setup lang="ts">
import { ref, computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { authService } from '@/shared/services/auth'
import { ApiError } from '@/shared/types/api'
import AuthShell from './AuthShell.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipLogo from '@/shared/ui/VipLogo.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const MIN_LENGTH = 12
const route = useRoute()
const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))

const password = ref('')
const confirm = ref('')
const submitting = ref(false)
const attempted = ref(false)
const done = ref(false)
const tokenError = ref('')

const passwordError = computed(() => {
  if (!attempted.value) return ''
  if (password.value.length < MIN_LENGTH) return `Use at least ${MIN_LENGTH} characters.`
  return ''
})
const confirmError = computed(() =>
  attempted.value && confirm.value !== password.value ? 'Passwords do not match.' : '',
)

async function submit() {
  attempted.value = true
  tokenError.value = ''
  if (passwordError.value || confirmError.value) return
  submitting.value = true
  try {
    await authService.confirmPasswordReset(token.value, password.value)
    done.value = true
  } catch (error) {
    const api = ApiError.from(error)
    if (api.code === 'PASSWORD_RESET_TOKEN_EXPIRED') {
      tokenError.value = 'This reset link has expired. Request a new one.'
    } else if (api.code === 'PASSWORD_RESET_TOKEN_INVALID') {
      tokenError.value = 'This reset link is invalid or has already been used.'
    } else if (api.code === 'PASSWORD_POLICY') {
      tokenError.value = api.message
    } else {
      tokenError.value = 'Could not reset your password. Please try again.'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthShell>
    <div class="authcard__brand"><VipLogo variant="full" size="lg" decorative /></div>
    <h1 class="authcard__title">Reset your password</h1>

    <VipAlert v-if="done" tone="success" title="Password updated">
      Your password has been changed and all existing sessions were signed out. You can now sign in with your new
      password.
    </VipAlert>

    <VipAlert v-else-if="!token" tone="danger" title="Invalid link">
      This password-reset link is missing or malformed. Request a new one to continue.
    </VipAlert>

    <template v-else>
      <p class="authcard__lead">Choose a new password for your account.</p>
      <VipAlert v-if="tokenError" tone="danger" title="Reset failed">{{ tokenError }}</VipAlert>
      <form class="authcard__form" novalidate @submit.prevent="submit">
        <VipInput
          v-model="password"
          label="New password"
          type="password"
          autocomplete="new-password"
          :help="`At least ${MIN_LENGTH} characters.`"
          :error="passwordError"
          :disabled="submitting"
          required
        />
        <VipInput
          v-model="confirm"
          label="Confirm new password"
          type="password"
          autocomplete="new-password"
          :error="confirmError"
          :disabled="submitting"
          required
        />
        <VipButton type="submit" variant="primary" size="lg" block :loading="submitting" :disabled="submitting">
          {{ submitting ? 'Updating…' : 'Set new password' }}
        </VipButton>
      </form>
    </template>

    <div class="authcard__links">
      <RouterLink v-if="done || !token || tokenError" class="authcard__back" to="/forgot-password">
        Request a new link
      </RouterLink>
      <RouterLink class="authcard__back" to="/login"
        ><VipIcon name="chevronLeft" :size="14" /> Back to sign in</RouterLink
      >
    </div>
  </AuthShell>
</template>

<style scoped>
.authcard__brand {
  display: flex;
  align-items: center;
  margin-bottom: var(--vip-sp-7);
  color: var(--vip-text-primary);
}
.authcard__title {
  font-size: var(--vip-fs-2xl);
  font-weight: var(--vip-fw-semibold);
  letter-spacing: -0.01em;
  line-height: 1.2;
  color: var(--vip-text-primary);
}
.authcard__lead {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-md);
  line-height: 1.6;
  margin: var(--vip-sp-3) 0 var(--vip-sp-7);
}
.authcard__form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.authcard__links {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
  margin-top: var(--vip-sp-7);
}
.authcard__back {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-brand-text);
  text-decoration: none;
  border-radius: var(--vip-radius-xs);
}
.authcard__back:hover {
  text-decoration: underline;
}
.authcard__title + :deep(.vip-alert) {
  margin-top: var(--vip-sp-6);
}
</style>
