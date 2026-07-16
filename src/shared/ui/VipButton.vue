<script setup lang="ts">
import { computed } from 'vue'
import VipIcon from './VipIcon.vue'

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'tertiary' | 'ghost' | 'danger'
    size?: 'xs' | 'sm' | 'md' | 'lg'
    icon?: string
    iconRight?: string
    loading?: boolean
    disabled?: boolean
    block?: boolean
    type?: 'button' | 'submit' | 'reset'
    active?: boolean
    title?: string
  }>(),
  { variant: 'secondary', size: 'md', type: 'button' },
)

const emit = defineEmits<{ click: [MouseEvent] }>()

const classes = computed(() => [
  'vip-btn',
  `vip-btn--${props.variant}`,
  `vip-btn--${props.size}`,
  { 'is-block': props.block, 'is-loading': props.loading, 'is-active': props.active },
])

function onClick(e: MouseEvent) {
  if (props.disabled || props.loading) return
  emit('click', e)
}
</script>

<template>
  <button :class="classes" :type="type" :disabled="disabled || loading" :title="title" @click="onClick">
    <span v-if="loading" class="vip-btn__spinner" aria-hidden="true" />
    <VipIcon v-else-if="icon" :name="icon" :size="size === 'lg' ? 17 : size === 'xs' ? 13 : 15" />
    <span v-if="$slots.default" class="vip-btn__label"><slot /></span>
    <VipIcon v-if="iconRight && !loading" :name="iconRight" :size="14" />
  </button>
</template>

<style scoped>
.vip-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--vip-sp-3);
  border: 1px solid transparent;
  border-radius: var(--vip-radius-md);
  font-weight: var(--vip-fw-medium);
  white-space: nowrap;
  transition: background var(--vip-motion-fast) var(--vip-ease-standard),
    border-color var(--vip-motion-fast) var(--vip-ease-standard),
    color var(--vip-motion-fast) var(--vip-ease-standard);
  user-select: none;
}
.vip-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.is-block {
  width: 100%;
}

.vip-btn--xs { height: 24px; padding: 0 var(--vip-sp-4); font-size: var(--vip-fs-xs); }
.vip-btn--sm { height: 28px; padding: 0 var(--vip-sp-5); font-size: var(--vip-fs-sm); }
.vip-btn--md { height: 32px; padding: 0 var(--vip-sp-6); font-size: var(--vip-fs-md); }
.vip-btn--lg { height: 40px; padding: 0 var(--vip-sp-7); font-size: var(--vip-fs-lg); }

.vip-btn--primary {
  background: var(--vip-brand-500);
  color: var(--vip-text-on-brand);
  border-color: var(--vip-brand-500);
}
.vip-btn--primary:hover:not(:disabled) { background: var(--vip-brand-600); border-color: var(--vip-brand-600); }

.vip-btn--secondary {
  background: var(--vip-surface-2);
  color: var(--vip-text-primary);
  border-color: var(--vip-border);
}
.vip-btn--secondary:hover:not(:disabled) { background: var(--vip-surface-hover); border-color: var(--vip-border-strong); }

.vip-btn--tertiary {
  background: transparent;
  color: var(--vip-text-secondary);
  border-color: var(--vip-border);
}
.vip-btn--tertiary:hover:not(:disabled) { background: var(--vip-surface-hover); color: var(--vip-text-primary); }

.vip-btn--ghost {
  background: transparent;
  color: var(--vip-text-secondary);
}
.vip-btn--ghost:hover:not(:disabled) { background: var(--vip-surface-hover); color: var(--vip-text-primary); }
.vip-btn--ghost.is-active { background: var(--vip-brand-soft); color: var(--vip-brand-text); }

.vip-btn--danger {
  background: var(--vip-danger);
  color: #fff;
  border-color: var(--vip-danger);
}
.vip-btn--danger:hover:not(:disabled) { filter: brightness(1.08); }

.vip-btn__spinner {
  width: 13px;
  height: 13px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: vip-btn-spin 0.7s linear infinite;
}
@keyframes vip-btn-spin {
  to { transform: rotate(360deg); }
}
</style>
