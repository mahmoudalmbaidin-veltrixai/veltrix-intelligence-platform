<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { authService } from '@/shared/services/auth'
import { useAuthStore } from '@/shared/stores/auth'
import { useUiStore } from '@/shared/stores/ui'
import { ApiError } from '@/shared/types/api'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipLogo from '@/shared/ui/VipLogo.vue'

const MIN_LENGTH = 12
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()

const current = ref('')
const password = ref('')
const confirm = ref('')
const submitting = ref(false)
const attempted = ref(false)
const serverError = ref('')

const currentError = computed(() => (attempted.value && !current.value ? 'Enter your current password.' : ''))
const passwordError = computed(() => {
  if (!attempted.value) return ''
  if (password.value.length < MIN_LENGTH) return `Use at least ${MIN_LENGTH} characters.`
  if (password.value === current.value) return 'Choose a password different from the current one.'
  return ''
})
const confirmError = computed(() =>
  attempted.value && confirm.value !== password.value ? 'Passwords do not match.' : '',
)

async function submit() {
  attempted.value = true
  serverError.value = ''
  if (currentError.value || passwordError.value || confirmError.value) return
  submitting.value = true
  try {
    await authService.changePassword(current.value, password.value)
    // Every session (including this one) is revoked server-side, so clear local
    // state and route to sign-in with the new credential.
    await auth.logout()
    ui.pushToast({
      kind: 'success',
      title: 'Password changed',
      message: 'Sign in with your new password to continue.',
    })
    await router.replace({ name: 'login' })
  } catch (error) {
    const api = ApiError.from(error)
    serverError.value =
      api.code === 'PASSWORD_POLICY'
        ? api.message
        : api.code === 'INVALID_CREDENTIALS'
          ? 'Your current password is incorrect.'
          : 'Could not change your password. Please try again.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="authpage">
    <div class="authpage__card">
      <VipLogo class="authpage__logo" />
      <h1 class="authpage__title">Set a new password</h1>
      <VipAlert tone="warning" title="Password change required">
        For your security, you must set a new password before you can continue.
      </VipAlert>

      <VipAlert v-if="serverError" tone="danger" title="Change failed">{{ serverError }}</VipAlert>

      <form class="authpage__form" novalidate @submit.prevent="submit">
        <VipInput
          v-model="current"
          label="Current password"
          type="password"
          autocomplete="current-password"
          :error="currentError"
          :disabled="submitting"
        />
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
          Change password
        </VipButton>
      </form>
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
  width: min(440px, 100%);
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
.authpage__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4, 16px);
}
</style>
