<script setup lang="ts">
import { watch, onBeforeUnmount } from 'vue'
import VipIcon from './VipIcon.vue'

const props = withDefaults(
  defineProps<{ open: boolean; title?: string; side?: 'right' | 'left'; width?: number }>(),
  { side: 'right', width: 440 },
)
const emit = defineEmits<{ close: [] }>()

watch(
  () => props.open,
  (v) => {
    document.body.style.overflow = v ? 'hidden' : ''
  },
)
onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="vip-drawer">
      <div v-if="open" class="vip-drawer__scrim" @click.self="emit('close')" @keydown.esc="emit('close')">
        <aside
          class="vip-drawer"
          :class="`is-${side}`"
          :style="{ width: `${width}px` }"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
        >
          <header class="vip-drawer__header">
            <h2 class="vip-drawer__title">{{ title }}</h2>
            <button type="button" class="vip-drawer__close" aria-label="Close" @click="emit('close')">
              <VipIcon name="close" :size="16" />
            </button>
          </header>
          <div class="vip-drawer__body"><slot /></div>
          <footer v-if="$slots.footer" class="vip-drawer__footer"><slot name="footer" /></footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.vip-drawer__scrim {
  position: fixed;
  inset: 0;
  background: var(--vip-scrim);
  z-index: var(--vip-z-drawer);
  display: flex;
}
.is-right { margin-left: auto; }
.vip-drawer {
  background: var(--vip-surface-1);
  border-left: 1px solid var(--vip-border);
  height: 100%;
  display: flex;
  flex-direction: column;
  max-width: 96vw;
  box-shadow: var(--vip-shadow-lg);
}
.is-left { border-left: none; border-right: 1px solid var(--vip-border); }
.vip-drawer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--vip-sp-6) var(--vip-sp-7);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.vip-drawer__title { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); }
.vip-drawer__close {
  width: 28px; height: 28px; display: inline-flex; align-items: center; justify-content: center;
  background: none; border: none; border-radius: var(--vip-radius-sm); color: var(--vip-text-muted);
}
.vip-drawer__close:hover { background: var(--vip-surface-hover); color: var(--vip-text-primary); }
.vip-drawer__body { flex: 1; overflow-y: auto; padding: var(--vip-sp-7); }
.vip-drawer__footer {
  display: flex; justify-content: flex-end; gap: var(--vip-sp-4);
  padding: var(--vip-sp-5) var(--vip-sp-7); border-top: 1px solid var(--vip-border-subtle);
}

.vip-drawer-enter-active, .vip-drawer-leave-active { transition: opacity var(--vip-motion-base); }
.vip-drawer-enter-active .vip-drawer, .vip-drawer-leave-active .vip-drawer { transition: transform var(--vip-motion-base) var(--vip-ease-emphasized); }
.vip-drawer-enter-from, .vip-drawer-leave-to { opacity: 0; }
.vip-drawer-enter-from .is-right, .vip-drawer-leave-to .is-right { transform: translateX(100%); }
.vip-drawer-enter-from .is-left, .vip-drawer-leave-to .is-left { transform: translateX(-100%); }
</style>
