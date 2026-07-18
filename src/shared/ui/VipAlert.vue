<script setup lang="ts">
import VipIcon from './VipIcon.vue'
withDefaults(defineProps<{ tone?: 'info' | 'success' | 'warning' | 'danger'; title?: string }>(), { tone: 'info' })
const icons = { info: 'info', success: 'success', warning: 'warning', danger: 'error' } as const
</script>

<template>
  <div class="vip-alert" :class="`is-${tone}`" role="alert">
    <VipIcon :name="icons[tone]" :size="16" class="vip-alert__icon" />
    <div class="vip-alert__content">
      <div v-if="title" class="vip-alert__title">{{ title }}</div>
      <div class="vip-alert__body"><slot /></div>
    </div>
    <div v-if="$slots.actions" class="vip-alert__actions"><slot name="actions" /></div>
  </div>
</template>

<style scoped>
.vip-alert {
  display: flex;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4) var(--vip-sp-5);
  border-radius: var(--vip-radius-md);
  border: 1px solid transparent;
  font-size: var(--vip-fs-sm);
}
.is-info {
  background: var(--vip-info-soft);
  color: var(--vip-info-text);
}
.is-success {
  background: var(--vip-success-soft);
  color: var(--vip-success-text);
}
.is-warning {
  background: var(--vip-warning-soft);
  color: var(--vip-warning-text);
}
.is-danger {
  background: var(--vip-danger-soft);
  color: var(--vip-danger-text);
}
.vip-alert__icon {
  flex: none;
  margin-top: 1px;
}
.vip-alert__content {
  flex: 1;
}
.vip-alert__title {
  font-weight: var(--vip-fw-semibold);
  margin-bottom: 2px;
}
.vip-alert__body {
  color: var(--vip-text-secondary);
}
.vip-alert__actions {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
}
</style>
