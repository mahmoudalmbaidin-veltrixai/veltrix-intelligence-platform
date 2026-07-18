<script setup lang="ts">
import VipIcon from './VipIcon.vue'
withDefaults(
  defineProps<{ icon?: string; title: string; description?: string; tone?: 'neutral' | 'danger' | 'warning' }>(),
  {
    icon: 'folder',
    tone: 'neutral',
  },
)
</script>

<template>
  <div class="vip-empty" :class="`is-${tone}`">
    <div class="vip-empty__icon"><VipIcon :name="icon" :size="26" /></div>
    <h3 class="vip-empty__title">{{ title }}</h3>
    <p v-if="description" class="vip-empty__desc">{{ description }}</p>
    <div v-if="$slots.default" class="vip-empty__actions"><slot /></div>
  </div>
</template>

<style scoped>
.vip-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--vip-sp-11) var(--vip-sp-7);
  gap: var(--vip-sp-4);
}
.vip-empty__icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-xl);
  color: var(--vip-text-muted);
  margin-bottom: var(--vip-sp-2);
}
.is-danger .vip-empty__icon {
  color: var(--vip-danger-text);
  background: var(--vip-danger-soft);
  border-color: transparent;
}
.is-warning .vip-empty__icon {
  color: var(--vip-warning-text);
  background: var(--vip-warning-soft);
  border-color: transparent;
}
.vip-empty__title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
}
.vip-empty__desc {
  font-size: var(--vip-fs-md);
  color: var(--vip-text-muted);
  max-width: 420px;
}
.vip-empty__actions {
  display: flex;
  gap: var(--vip-sp-4);
  margin-top: var(--vip-sp-4);
}
</style>
