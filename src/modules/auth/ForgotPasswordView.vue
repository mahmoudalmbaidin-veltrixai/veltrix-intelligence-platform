<script setup lang="ts">
import { ref, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { authService } from '@/shared/services/auth'
import AuthShell from './AuthShell.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipLogo from '@/shared/ui/VipLogo.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

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
  <AuthShell>
    <div class="authcard__brand"><VipLogo variant="full" size="lg" decorative /></div>
    <h1 class="authcard__title">Reset your password</h1>

    <VipAlert v-if="sent" tone="success" title="Request received">
      If an account matches that username or email, your password-reset request has been recorded. Please contact your
      organization administrator to complete the reset.
    </VipAlert>

    <template v-else>
      <p class="authcard__lead">
        Enter your username or email to request a password reset. Your organization administrator can help you complete
        it.
      </p>
      <form class="authcard__form" novalidate @submit.prevent="submit">
        <VipInput
          v-model="identifier"
          label="Username or email"
          type="text"
          name="username"
          autocomplete="username"
          icon="users"
          placeholder="your.username"
          :error="identifierError"
          :disabled="submitting"
          required
        />
        <VipButton type="submit" variant="primary" size="lg" block :loading="submitting" :disabled="submitting">
          {{ submitting ? 'Requesting…' : 'Request password reset' }}
        </VipButton>
      </form>
    </template>

    <RouterLink class="authcard__back" to="/login"
      ><VipIcon name="chevronLeft" :size="14" /> Back to sign in</RouterLink
    >
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
.authcard__back {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  margin-top: var(--vip-sp-7);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-brand-text);
  text-decoration: none;
  border-radius: var(--vip-radius-xs);
}
.authcard__back:hover {
  text-decoration: underline;
}
/* Space the alert from the heading, and the back-link below it. */
.authcard__title + :deep(.vip-alert) {
  margin-top: var(--vip-sp-6);
}
</style>
