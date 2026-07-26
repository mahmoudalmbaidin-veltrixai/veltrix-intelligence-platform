<script setup lang="ts">
import { computed, ref } from 'vue'
const props = withDefaults(
  defineProps<{
    text: string
    /** Optional secondary line rendered beneath the title (richer tooltip). */
    description?: string
    /** Optional keyboard shortcut rendered as a kbd chip. */
    shortcut?: string
    placement?: 'top' | 'right' | 'bottom' | 'left'
  }>(),
  { placement: 'top' },
)
const show = ref(false)
// Show whenever there is any content to display.
const hasContent = computed(() => !!(props.text || props.description || props.shortcut))
const isRich = computed(() => !!(props.description || props.shortcut))
</script>

<template>
  <span
    class="vip-tt"
    @mouseenter="show = true"
    @mouseleave="show = false"
    @focusin="show = true"
    @focusout="show = false"
  >
    <slot />
    <span
      v-if="show && hasContent"
      class="vip-tt__bubble"
      :class="[`is-${placement}`, { 'is-rich': isRich }]"
      role="tooltip"
    >
      <template v-if="isRich">
        <span v-if="text" class="vip-tt__title">{{ text }}</span>
        <span v-if="description" class="vip-tt__desc">{{ description }}</span>
        <kbd v-if="shortcut" class="vip-tt__kbd">{{ shortcut }}</kbd>
      </template>
      <template v-else>{{ text }}</template>
    </span>
  </span>
</template>

<style scoped>
.vip-tt {
  position: relative;
  display: inline-flex;
}
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
.vip-tt__bubble.is-rich {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--vip-sp-2);
  white-space: normal;
  width: max-content;
  max-width: 240px;
  padding: var(--vip-sp-4) var(--vip-sp-5);
}
.vip-tt__title {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
}
.vip-tt__desc {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  line-height: 1.4;
}
.vip-tt__kbd {
  margin-top: 2px;
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-2xs);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  color: var(--vip-text-secondary);
  padding: 1px 6px;
  border-radius: var(--vip-radius-xs);
}
.is-top {
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
}
.is-bottom {
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
}
.is-right {
  left: calc(100% + 6px);
  top: 50%;
  transform: translateY(-50%);
}
.is-left {
  right: calc(100% + 6px);
  top: 50%;
  transform: translateY(-50%);
}
</style>
