<script setup lang="ts">
/**
 * Elegant lightweight overlay for a heavier module refresh. Keeps existing
 * content visible underneath (subtle dim + optional blur), announces politely,
 * and honours reduced-motion. Use sparingly — most refreshes should use
 * skeletons or the inline RefreshIndicator instead.
 */
import VipLogo from '@/shared/ui/VipLogo.vue'

withDefaults(
  defineProps<{
    open?: boolean
    title?: string
    message?: string
  }>(),
  { open: false, title: 'Refreshing your workspace', message: 'Getting the latest data ready…' },
)
</script>

<template>
  <Transition name="vip-refresh-fade">
    <div v-if="open" class="vip-refresh-overlay" role="status" aria-live="polite">
      <div class="vip-refresh-overlay__panel">
        <div class="vip-refresh-overlay__mark"><VipLogo variant="icon" size="lg" /></div>
        <p class="vip-refresh-overlay__title">{{ title }}</p>
        <p class="vip-refresh-overlay__message">{{ message }}</p>
        <div class="vip-refresh-overlay__bar"><span /></div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.vip-refresh-overlay {
  position: absolute;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--vip-surface-1, #0b0d12) 62%, transparent);
  backdrop-filter: blur(3px);
}
.vip-refresh-overlay__panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--vip-sp-3);
  text-align: center;
  padding: var(--vip-sp-6);
}
.vip-refresh-overlay__mark {
  animation: vip-refresh-pulse 1.8s ease-in-out infinite;
}
.vip-refresh-overlay__title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
}
.vip-refresh-overlay__message {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.vip-refresh-overlay__bar {
  width: 180px;
  height: 3px;
  border-radius: 999px;
  overflow: hidden;
  background: color-mix(in srgb, var(--vip-brand-500) 20%, transparent);
}
.vip-refresh-overlay__bar span {
  display: block;
  height: 100%;
  width: 40%;
  border-radius: inherit;
  background: var(--vip-brand-500);
  animation: vip-refresh-track 1.2s ease-in-out infinite;
}
.vip-refresh-fade-enter-active,
.vip-refresh-fade-leave-active {
  transition: opacity 200ms ease;
}
.vip-refresh-fade-enter-from,
.vip-refresh-fade-leave-to {
  opacity: 0;
}
@keyframes vip-refresh-pulse {
  0%,
  100% {
    opacity: 0.7;
    transform: scale(0.97);
  }
  50% {
    opacity: 1;
    transform: scale(1.02);
  }
}
@keyframes vip-refresh-track {
  0% {
    transform: translateX(-120%);
  }
  100% {
    transform: translateX(360%);
  }
}
@media (prefers-reduced-motion: reduce) {
  .vip-refresh-overlay__mark,
  .vip-refresh-overlay__bar span {
    animation: none;
  }
  .vip-refresh-overlay__bar span {
    width: 100%;
  }
}
:global(html[data-reduced-motion]) .vip-refresh-overlay__mark,
:global(html[data-reduced-motion]) .vip-refresh-overlay__bar span {
  animation: none;
}
</style>
