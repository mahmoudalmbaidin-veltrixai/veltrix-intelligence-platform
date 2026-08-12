<script setup lang="ts">
/**
 * Idle-timeout warning. Mounted once at the app root; it stays inert until the
 * idle deadline approaches, then shows a restrained countdown with an explicit
 * choice. Uses the shared VIP dialog (no native alert/confirm) and is keyboard-
 * and screen-reader accessible.
 */
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import { useIdleSession } from '@/shared/composables/useIdleSession'

const { showWarning, countdownLabel, staySignedIn, signOutNow } = useIdleSession()
</script>

<template>
  <VipDialog
    :open="showWarning"
    title="Session expiring"
    description="You've been inactive for a while."
    size="sm"
    :closable="false"
    @close="staySignedIn"
  >
    <div class="session-expiry" role="alertdialog" aria-live="assertive">
      <p class="session-expiry__lead">For your security, you'll be signed out in:</p>
      <p class="session-expiry__countdown" aria-label="Time remaining">{{ countdownLabel }}</p>
      <p class="session-expiry__hint">Choose “Stay signed in” to continue where you left off.</p>
    </div>
    <template #footer>
      <VipButton variant="tertiary" @click="signOutNow">Sign out</VipButton>
      <VipButton variant="primary" icon="check" @click="staySignedIn">Stay signed in</VipButton>
    </template>
  </VipDialog>
</template>

<style scoped>
.session-expiry {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--vip-sp-3);
  text-align: center;
  padding: var(--vip-sp-2) 0;
}
.session-expiry__lead {
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-sm);
}
.session-expiry__countdown {
  font-size: var(--vip-fs-2xl, 2rem);
  font-weight: var(--vip-fw-semibold);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  color: var(--vip-text-primary);
}
.session-expiry__hint {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-xs);
}
</style>
