<script setup lang="ts">
import { useUiStore } from '@/shared/stores/ui'
import VipIcon from './VipIcon.vue'

const ui = useUiStore()
const iconFor = { success: 'success', error: 'error', warning: 'warning', info: 'info' } as const
</script>

<template>
  <Teleport to="body">
    <!--
      Landmark region only — NOT a live region. Screen-reader announcements are
      the sole responsibility of the global announcer (AriaLive via announce()),
      which composes one polite/assertive message per toast. Making this a second
      aria-live region caused every toast to be announced twice (CERT-P2-004).
    -->
    <div class="vip-toasts" role="region" aria-label="Notifications">
      <TransitionGroup name="vip-toast">
        <div v-for="t in ui.toasts" :key="t.id" class="vip-toast" :class="`is-${t.kind}`">
          <VipIcon :name="iconFor[t.kind]" :size="18" class="vip-toast__icon" />
          <div class="vip-toast__body">
            <div class="vip-toast__title">{{ t.title }}</div>
            <div v-if="t.message" class="vip-toast__msg">{{ t.message }}</div>
            <div v-if="t.correlationId" class="vip-toast__cid">ID: {{ t.correlationId }}</div>
          </div>
          <button type="button" class="vip-toast__close" aria-label="Dismiss" @click="ui.dismissToast(t.id)">
            <VipIcon name="close" :size="14" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.vip-toasts {
  position: fixed;
  bottom: var(--vip-sp-7);
  right: var(--vip-sp-7);
  z-index: var(--vip-z-toast);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
  max-width: 380px;
}
.vip-toast {
  display: flex;
  gap: var(--vip-sp-4);
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-left: 3px solid var(--vip-border-strong);
  border-radius: var(--vip-radius-md);
  padding: var(--vip-sp-5) var(--vip-sp-5);
  box-shadow: var(--vip-shadow-lg);
}
.vip-toast.is-success {
  border-left-color: var(--vip-success);
}
.vip-toast.is-error {
  border-left-color: var(--vip-danger);
}
.vip-toast.is-warning {
  border-left-color: var(--vip-warning);
}
.vip-toast.is-info {
  border-left-color: var(--vip-info);
}
.vip-toast.is-success .vip-toast__icon {
  color: var(--vip-success-text);
}
.vip-toast.is-error .vip-toast__icon {
  color: var(--vip-danger-text);
}
.vip-toast.is-warning .vip-toast__icon {
  color: var(--vip-warning-text);
}
.vip-toast.is-info .vip-toast__icon {
  color: var(--vip-info-text);
}
.vip-toast__body {
  flex: 1;
  min-width: 0;
}
.vip-toast__title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
}
.vip-toast__msg {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin-top: 2px;
}
.vip-toast__cid {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-disabled);
  font-family: var(--vip-font-mono);
  margin-top: 4px;
}
.vip-toast__close {
  flex: none;
  width: 22px;
  height: 22px;
  background: none;
  border: none;
  color: var(--vip-text-muted);
  border-radius: var(--vip-radius-sm);
}
.vip-toast__close:hover {
  background: var(--vip-surface-hover);
}

.vip-toast-enter-active,
.vip-toast-leave-active {
  transition: all var(--vip-motion-base) var(--vip-ease-emphasized);
}
.vip-toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}
.vip-toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}
</style>
