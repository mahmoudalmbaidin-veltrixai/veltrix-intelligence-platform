<script setup lang="ts">
import { watch, ref, nextTick, onBeforeUnmount } from 'vue'
import VipIcon from './VipIcon.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    description?: string
    size?: 'sm' | 'md' | 'lg' | 'xl'
    closable?: boolean
  }>(),
  { size: 'md', closable: true },
)
const emit = defineEmits<{ close: [] }>()

const panel = ref<HTMLElement>()
let lastFocused: HTMLElement | null = null

function close() {
  if (props.closable) emit('close')
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
  if (e.key === 'Tab') trapFocus(e)
}
function trapFocus(e: KeyboardEvent) {
  if (!panel.value) return
  const focusables = panel.value.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
  )
  if (!focusables.length) return
  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

watch(
  () => props.open,
  async (v) => {
    if (v) {
      lastFocused = document.activeElement as HTMLElement
      document.body.style.overflow = 'hidden'
      await nextTick()
      panel.value?.querySelector<HTMLElement>('[data-autofocus], button, input, textarea, select')?.focus()
    } else {
      document.body.style.overflow = ''
      lastFocused?.focus()
    }
  },
)
onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="vip-dialog">
      <div v-if="open" class="vip-dialog__scrim" @click.self="close" @keydown="onKeydown">
        <div
          ref="panel"
          class="vip-dialog"
          :class="`vip-dialog--${size}`"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
        >
          <header v-if="title || closable" class="vip-dialog__header">
            <div>
              <h2 v-if="title" class="vip-dialog__title">{{ title }}</h2>
              <p v-if="description" class="vip-dialog__desc">{{ description }}</p>
            </div>
            <button v-if="closable" type="button" class="vip-dialog__close" aria-label="Close" @click="close">
              <VipIcon name="close" :size="16" />
            </button>
          </header>
          <div class="vip-dialog__body"><slot /></div>
          <footer v-if="$slots.footer" class="vip-dialog__footer"><slot name="footer" /></footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.vip-dialog__scrim {
  position: fixed;
  inset: 0;
  background: var(--vip-scrim);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 10vh var(--vip-sp-6) var(--vip-sp-6);
  z-index: var(--vip-z-modal);
  overflow-y: auto;
}
.vip-dialog {
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-xl);
  box-shadow: var(--vip-shadow-lg);
  width: 100%;
  display: flex;
  flex-direction: column;
  max-height: 80vh;
}
.vip-dialog--sm {
  max-width: 420px;
}
.vip-dialog--md {
  max-width: 560px;
}
.vip-dialog--lg {
  max-width: 760px;
}
.vip-dialog--xl {
  max-width: 1040px;
}
.vip-dialog__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--vip-sp-6);
  padding: var(--vip-sp-7) var(--vip-sp-7) var(--vip-sp-5);
}
.vip-dialog__title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
}
.vip-dialog__desc {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin-top: var(--vip-sp-2);
}
.vip-dialog__close {
  flex: none;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
}
.vip-dialog__close:hover {
  background: var(--vip-surface-hover);
  color: var(--vip-text-primary);
}
.vip-dialog__body {
  padding: 0 var(--vip-sp-7) var(--vip-sp-7);
  overflow-y: auto;
}
.vip-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-5) var(--vip-sp-7);
  border-top: 1px solid var(--vip-border-subtle);
}

.vip-dialog-enter-active,
.vip-dialog-leave-active {
  transition: opacity var(--vip-motion-base);
}
.vip-dialog-enter-active .vip-dialog,
.vip-dialog-leave-active .vip-dialog {
  transition: transform var(--vip-motion-base) var(--vip-ease-emphasized);
}
.vip-dialog-enter-from,
.vip-dialog-leave-to {
  opacity: 0;
}
.vip-dialog-enter-from .vip-dialog,
.vip-dialog-leave-to .vip-dialog {
  transform: translateY(-12px) scale(0.98);
}
</style>
