<script setup lang="ts">
import { ref, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { authService } from '@/shared/services/auth'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipLogo from '@/shared/ui/VipLogo.vue'

const identifier = ref('')
const submitting = ref(false)
const attempted = ref(false)
const sent = ref(false)

const identifierError = computed(() =>
  attempted.value && !identifier.value.trim() ? 'Enter your username or email.' : '',
)

async function submit() {
  attempted.value = true
  if (!identifier.value.trim()) return
  submitting.value = true
  try {
    // The response is deliberately uniform whether or not the account exists,
    // so success is shown regardless — we never reveal account existence.
    await authService.requestPasswordReset(identifier.value.trim())
    sent.value = true
  } catch {
    // Even on an unexpected error we avoid disclosing state; show the same
    // confirmation so the page cannot be used as an account oracle.
    sent.value = true
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="authpage">
    <div class="authpage__card">
      <VipLogo class="authpage__logo" />
      <h1 class="authpage__title">Forgot your password?</h1>

      <VipAlert v-if="sent" tone="success" title="Check your email">
        If an account matches that username or email, a password-reset link has been sent. The link expires shortly and
        can be used once.
      </VipAlert>

      <template v-else>
        <p class="authpage__lead">Enter your username or email and we'll send a link to reset your password.</p>
        <form class="authpage__form" novalidate @submit.prevent="submit">
          <VipInput
            v-model="identifier"
            label="Username or email"
            type="text"
            autocomplete="username"
            :error="identifierError"
            :disabled="submitting"
          />
          <VipButton type="submit" variant="primary" size="lg" block :loading="submitting" :disabled="submitting">
            Send reset link
          </VipButton>
        </form>
      </template>

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
