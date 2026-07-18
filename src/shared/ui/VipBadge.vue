<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    tone?: 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info'
    variant?: 'soft' | 'solid' | 'outline' | 'dot'
    size?: 'sm' | 'md'
  }>(),
  { tone: 'neutral', variant: 'soft', size: 'md' },
)

const classes = computed(() => [
  'vip-badge',
  `vip-badge--${props.tone}`,
  `vip-badge--${props.variant}`,
  `vip-badge--${props.size}`,
])
</script>

<template>
  <span :class="classes">
    <span v-if="variant === 'dot'" class="vip-badge__dot" />
    <slot />
  </span>
</template>

<style scoped>
.vip-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
  border-radius: var(--vip-radius-full);
  font-weight: var(--vip-fw-medium);
  white-space: nowrap;
  line-height: 1;
}
.vip-badge--sm {
  padding: 2px 7px;
  font-size: var(--vip-fs-2xs);
}
.vip-badge--md {
  padding: 3px 9px;
  font-size: var(--vip-fs-xs);
}

.vip-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.vip-badge--dot {
  background: var(--vip-surface-2);
  color: var(--vip-text-secondary);
  border: 1px solid var(--vip-border);
}

/* soft */
.vip-badge--soft.vip-badge--neutral {
  background: var(--vip-surface-3);
  color: var(--vip-text-secondary);
}
.vip-badge--soft.vip-badge--brand {
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.vip-badge--soft.vip-badge--success {
  background: var(--vip-success-soft);
  color: var(--vip-success-text);
}
.vip-badge--soft.vip-badge--warning {
  background: var(--vip-warning-soft);
  color: var(--vip-warning-text);
}
.vip-badge--soft.vip-badge--danger {
  background: var(--vip-danger-soft);
  color: var(--vip-danger-text);
}
.vip-badge--soft.vip-badge--info {
  background: var(--vip-info-soft);
  color: var(--vip-info-text);
}

/* solid */
.vip-badge--solid.vip-badge--neutral {
  background: var(--vip-text-muted);
  color: var(--vip-text-inverse);
}
.vip-badge--solid.vip-badge--brand {
  background: var(--vip-brand-500);
  color: #fff;
}
.vip-badge--solid.vip-badge--success {
  background: var(--vip-success);
  color: #fff;
}
.vip-badge--solid.vip-badge--warning {
  background: var(--vip-warning);
  color: #fff;
}
.vip-badge--solid.vip-badge--danger {
  background: var(--vip-danger);
  color: #fff;
}
.vip-badge--solid.vip-badge--info {
  background: var(--vip-info);
  color: #fff;
}

/* outline */
.vip-badge--outline {
  background: transparent;
  border: 1px solid var(--vip-border-strong);
  color: var(--vip-text-secondary);
}
</style>
