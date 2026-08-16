<script setup lang="ts">
withDefaults(defineProps<{ padded?: boolean; hoverable?: boolean; inset?: boolean }>(), {
  padded: true,
})
</script>

<template>
  <div class="vip-card" :class="{ 'is-padded': padded, 'is-hoverable': hoverable, 'is-inset': inset }">
    <slot />
    <div v-if="$slots.footer" class="vip-card__footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<style scoped>
.vip-card {
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-lg);
}
.vip-card__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--vip-sp-4);
  width: 100%;
  margin-top: var(--vip-sp-6);
  padding-top: var(--vip-sp-6);
  border-top: 1px solid var(--vip-border-subtle);
}
.is-padded {
  padding: var(--vip-sp-7);
}
.is-inset {
  background: var(--vip-surface-2);
}
.is-hoverable {
  cursor: pointer;
  transition:
    border-color var(--vip-motion-fast) var(--vip-ease-standard),
    background var(--vip-motion-fast) var(--vip-ease-standard);
}
.is-hoverable:hover {
  border-color: var(--vip-border-strong);
  background: var(--vip-surface-2);
}
</style>
