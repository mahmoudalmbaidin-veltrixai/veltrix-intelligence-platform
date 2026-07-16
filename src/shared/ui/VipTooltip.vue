<script setup lang="ts">
import { ref } from 'vue'
withDefaults(defineProps<{ text: string; placement?: 'top' | 'right' | 'bottom' | 'left' }>(), { placement: 'top' })
const show = ref(false)
</script>

<template>
  <span class="vip-tt" @mouseenter="show = true" @mouseleave="show = false" @focusin="show = true" @focusout="show = false">
    <slot />
    <span v-if="show && text" class="vip-tt__bubble" :class="`is-${placement}`" role="tooltip">{{ text }}</span>
  </span>
</template>

<style scoped>
.vip-tt { position: relative; display: inline-flex; }
.vip-tt__bubble {
  position: absolute;
  z-index: var(--vip-z-tooltip);
  background: var(--vip-surface-3);
  color: var(--vip-text-primary);
  border: 1px solid var(--vip-border);
  padding: var(--vip-sp-2) var(--vip-sp-4);
  border-radius: var(--vip-radius-sm);
  font-size: var(--vip-fs-xs);
  white-space: nowrap;
  box-shadow: var(--vip-shadow-md);
  pointer-events: none;
}
.is-top { bottom: calc(100% + 6px); left: 50%; transform: translateX(-50%); }
.is-bottom { top: calc(100% + 6px); left: 50%; transform: translateX(-50%); }
.is-right { left: calc(100% + 6px); top: 50%; transform: translateY(-50%); }
.is-left { right: calc(100% + 6px); top: 50%; transform: translateY(-50%); }
</style>
