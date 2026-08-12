<script setup lang="ts">
/**
 * Smallest appropriate loading treatment for a component/data refresh: an inline
 * spinning glyph with an optional label and success/error states. Use for
 * "refresh this table / chart / list" actions instead of a blocking overlay.
 */
import { computed } from 'vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const props = withDefaults(
  defineProps<{
    state?: 'idle' | 'refreshing' | 'success' | 'error'
    label?: string
    /** Optional retry handler; when provided the error state offers a Try again. */
    onRetry?: () => void
  }>(),
  { state: 'idle', label: '' },
)

const text = computed(() => {
  if (props.label) return props.label
  return props.state === 'refreshing'
    ? 'Refreshing…'
    : props.state === 'success'
      ? 'Up to date'
      : props.state === 'error'
        ? "Couldn't refresh"
        : ''
})
const icon = computed(() => (props.state === 'success' ? 'check' : props.state === 'error' ? 'warning' : 'refresh'))
</script>

<template>
  <span v-if="state !== 'idle'" class="vip-refresh-indicator" :class="`is-${state}`" role="status" aria-live="polite">
    <VipIcon :name="icon" :size="14" :class="{ 'is-spinning': state === 'refreshing' }" />
    <span class="vip-refresh-indicator__text">{{ text }}</span>
    <button v-if="state === 'error' && onRetry" type="button" class="vip-refresh-indicator__retry" @click="onRetry">
      Try again
    </button>
  </span>
</template>

<style scoped>
.vip-refresh-indicator {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.vip-refresh-indicator.is-success {
  color: var(--vip-success-text, var(--vip-text-secondary));
}
.vip-refresh-indicator.is-error {
  color: var(--vip-danger-text);
}
.vip-refresh-indicator :deep(.is-spinning) {
  animation: vip-refresh-spin 0.9s linear infinite;
}
.vip-refresh-indicator__retry {
  background: none;
  border: none;
  padding: 0;
  margin-left: var(--vip-sp-1);
  color: var(--vip-brand-text, var(--vip-brand-500));
  font: inherit;
  cursor: pointer;
  text-decoration: underline;
}
@keyframes vip-refresh-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .vip-refresh-indicator :deep(.is-spinning) {
    animation: none;
  }
}
:global(html[data-reduced-motion]) .vip-refresh-indicator :deep(.is-spinning) {
  animation: none;
}
</style>
