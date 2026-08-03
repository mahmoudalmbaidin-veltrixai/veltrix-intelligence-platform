<script setup lang="ts">
import { ref, computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { authService } from '@/shared/services/auth'
import { ApiError } from '@/shared/types/api'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipLogo from '@/shared/ui/VipLogo.vue'

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
  <div class="authpage">
    <div class="authpage__card">
      <VipLogo class="authpage__logo" />
      <h1 class="authpage__title">Reset your password</h1>

      <VipAlert v-if="done" tone="success" title="Password updated">
        Your password has been changed and all existing sessions were signed out. You can now sign in with your new
        password.
      </VipAlert>

      <VipAlert v-else-if="!token" tone="danger" title="Invalid link">
        This password-reset link is missing or malformed. Request a new one to continue.
      </VipAlert>

      <template v-else>
        <p class="authpage__lead">Choose a new password for your account.</p>
        <VipAlert v-if="tokenError" tone="danger" title="Reset failed">{{ tokenError }}</VipAlert>
        <form class="authpage__form" novalidate @submit.prevent="submit">
          <VipInput
            v-model="password"
            label="New password"
            type="password"
            autocomplete="new-password"
            :hint="`At least ${MIN_LENGTH} characters.`"
            :error="passwordError"
            :disabled="submitting"
          />
          <VipInput
            v-model="confirm"
            label="Confirm new password"
            type="password"
            autocomplete="new-password"
            :error="confirmError"
            :disabled="submitting"
          />
          <VipButton type="submit" variant="primary" size="lg" block :loading="submitting" :disabled="submitting">
            Set new password
          </VipButton>
        </form>
      </template>

      <RouterLink v-if="done || !token || tokenError" class="authpage__back" to="/forgot-password">
        Request a new link
      </RouterLink>
      <RouterLink class="authpage__back" to="/login">Back to sign in</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.authpage {
  display: grid;
  place-items: center;
  min-height: 100vh;
  padding: var(--space-6, 24px);
}
.authpage__card {
  width: min(420px, 100%);
  display: flex;
  flex-direction: column;
  gap: var(--space-4, 16px);
  padding: var(--space-6, 24px);
  background: var(--surface-1, #fff);
  border: 1px solid var(--border-subtle, #e2e8f0);
  border-radius: var(--radius-lg, 12px);
}
.authpage__logo {
  height: 40px;
}
.authpage__title {
  margin: 0;
  font-size: var(--font-size-xl, 1.4rem);
}
.authpage__lead {
  margin: 0;
  color: var(--text-muted, #64748b);
}
.authpage__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4, 16px);
}
.authpage__back {
  text-align: center;
  color: var(--brand-600, #2563eb);
  text-decoration: none;
}
.authpage__back:hover {
  text-decoration: underline;
}
</style>
